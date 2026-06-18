#!/usr/bin/env python3
"""
Upgrade a ClickUp comment from plain comment_text to native rich-text ops.

The ClickUp MCP (clickup_create_task_comment) only writes comment_text — a plain string
that barely renders markdown. Native formatting (headers, bold, lists, code blocks) lives
in the `comment` field: an array of Quill-delta-style ops documented at:
https://developer.clickup.com/docs/comment-formatting

This script:
  1. Preprocesses the skill's plain-text dialect into pseudo-markdown
  2. Parses that markdown into ClickUp comment ops
  3. PUTs {"comment": [...ops]} to /api/v2/comment/{comment_id}

Requires CLICKUP_API_TOKEN (Personal API Token, pk_...) — the MCP OAuth token is not
accessible to local hooks.

Stdlib only. No external dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

API_TIMEOUT_SEC = 10
DIVIDER_RE = re.compile(r"^[\u2500\-─]{40,}\s*$")
WARNING_LINES = frozenset({"IMPORTANTE", "OBSOLETO", "MUST", "WARNING", "NOTE"})
URL_RE = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)
LINK_MD_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


class DeltaWriter:
    """
    Emits ClickUp comment ops. Block attributes (header, list, code-block, blockquote)
    ride on the trailing newline for that line; inline attributes ride on text spans.
    """

    def __init__(self) -> None:
        self.blocks: list[dict] = []

    def append(self, text: str, attrs: dict | None = None) -> None:
        if not text:
            return
        block: dict = {"text": text}
        if attrs:
            block["attributes"] = dict(attrs)
        self.blocks.append(block)

    def append_paragraph_break(self, attrs: dict | None = None) -> None:
        self.append("\n", attrs)

    def parse_inline(self, text: str, base_attrs: dict | None = None) -> None:
        """Parse inline markdown: **bold**, __underline__, `code`, [text](url), raw URLs."""
        pos = 0
        attrs = base_attrs or {}

        while pos < len(text):
            # Fenced inline is handled at block level; here we handle backtick spans.
            if text[pos] == "`":
                end = text.find("`", pos + 1)
                if end == -1:
                    break
                inner = text[pos + 1:end]
                merged = {**attrs, "code": True}
                self.append(inner, merged)
                pos = end + 1
                continue

            # Bold **text**
            if text.startswith("**", pos):
                end = text.find("**", pos + 2)
                if end != -1:
                    inner = text[pos + 2:end]
                    self.parse_inline(inner, {**attrs, "bold": True})
                    pos = end + 2
                    continue

            # Underline __text__
            if text.startswith("__", pos):
                end = text.find("__", pos + 2)
                if end != -1:
                    inner = text[pos + 2:end]
                    self.parse_inline(inner, {**attrs, "underline": True})
                    pos = end + 2
                    continue

            # Markdown link [text](url)
            link_match = LINK_MD_RE.match(text, pos)
            if link_match:
                link_text, url = link_match.group(1), link_match.group(2)
                self.parse_inline(link_text, {**attrs, "link": url})
                pos = link_match.end()
                continue

            # Find next special char or URL
            next_special = len(text)
            for marker in ("`", "**", "__", "["):
                idx = text.find(marker, pos)
                if idx != -1:
                    next_special = min(next_special, idx)

            url_match = URL_RE.search(text, pos)
            if url_match and url_match.start() < next_special:
                if url_match.start() > pos:
                    self.append(text[pos:url_match.start()], attrs)
                url = url_match.group(0)
                self.append(url, {**attrs, "link": url})
                pos = url_match.end()
                continue

            chunk = text[pos:next_special]
            if chunk:
                self.append(chunk, attrs)
            pos = next_special if next_special > pos else pos + 1

    def parse_heading_line(self, line: str, level: int) -> None:
        content = re.sub(r"^#{1,6}\s+", "", line).strip()
        self.parse_inline(content)
        self.append_paragraph_break({"header": level})

    def parse_blockquote_line(self, line: str) -> None:
        content = line[2:] if line.startswith("> ") else line
        self.parse_inline(content)
        self.append_paragraph_break({"blockquote": True})

    def parse_list_item(
        self, content: str, list_type: str, indent: int
    ) -> None:
        self.parse_inline(content)
        attrs: dict = {"list": list_type}
        if indent > 0:
            attrs["indent"] = indent
        self.append_paragraph_break(attrs)

    def parse_plain_paragraph(self, line: str) -> None:
        self.parse_inline(line)
        self.append_paragraph_break()

    def emit_code_line(self, line: str) -> None:
        self.append(line)
        self.append_paragraph_break({"code-block": True})


def preprocess_plain_text(text: str) -> str:
    """
    Convert the clickup-comment-style plain-text dialect into pseudo-markdown
    that our block parser understands.

    Mappings:
      • divider / title [/ divider]    → ## header (level 2); dividers dropped
      • standalone 40+ box divider     → dropped (renders as a stray rule)
      • • bullet                       → - markdown bullet
      • – sub-bullet with indent       → nested - bullet
      • 4-space indented blocks        → fenced code block
      • standalone IMPORTANTE/MUST/... → **IMPORTANTE** (bold)
    """
    lines = text.splitlines()
    out_lines: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Box divider — collapse a divider-wrapped section title into a single
        # header and DROP the dividers. Emitting the dividers as content makes
        # ClickUp render stray separator lines around the title (the bug seen
        # inside numbered sections). Handles both the canonical
        # `divider / title / divider` and a `divider / title` with the closing
        # divider missing.
        if DIVIDER_RE.match(stripped):
            title_line = lines[i + 1].strip() if i + 1 < n else ""
            is_title = (
                bool(title_line)
                and not DIVIDER_RE.match(title_line)
                and not title_line.startswith(("•", "–", "-", "*"))
            )
            if is_title:
                out_lines.append(f"## {title_line}")
                i += 2
                # consume the optional closing divider
                if i < n and DIVIDER_RE.match(lines[i].strip()):
                    i += 1
                continue
            # standalone divider with no title following → drop it
            i += 1
            continue

        # Standalone warning → bold
        if stripped in WARNING_LINES:
            out_lines.append(f"**{stripped}**")
            i += 1
            continue

        # 4-space indented code block (consecutive lines)
        if line.startswith("    ") and line.strip():
            code_lines: list[str] = []
            while i < n and (lines[i].startswith("    ") or lines[i].strip() == ""):
                if lines[i].strip():
                    code_lines.append(lines[i][4:])
                elif code_lines:
                    code_lines.append("")
                i += 1
            out_lines.append("```")
            out_lines.extend(code_lines)
            out_lines.append("```")
            continue

        # Bullet •
        bullet_match = re.match(r"^(\s*)•\s+(.*)$", line)
        if bullet_match:
            indent_spaces = len(bullet_match.group(1))
            indent_level = max(0, indent_spaces // 2)
            prefix = "  " * indent_level
            out_lines.append(f"{prefix}- {bullet_match.group(2)}")
            i += 1
            continue

        # Sub-bullet – (en dash)
        sub_match = re.match(r"^(\s*)–\s+(.*)$", line)
        if sub_match:
            indent_spaces = len(sub_match.group(1))
            indent_level = max(1, indent_spaces // 2)
            prefix = "  " * indent_level
            out_lines.append(f"{prefix}- {sub_match.group(2)}")
            i += 1
            continue

        out_lines.append(line)
        i += 1

    return "\n".join(out_lines)


def markdown_to_blocks(text: str) -> list[dict]:
    """Line-based markdown parser → ClickUp comment ops."""
    writer = DeltaWriter()
    lines = text.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Fenced code block
        if stripped.startswith("```"):
            fence_lang = stripped[3:].strip()
            code_lines: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1  # skip closing fence
            for code_line in code_lines:
                writer.emit_code_line(code_line)
            continue

        if not stripped:
            i += 1
            continue

        # Thematic break
        if stripped in ("---", "***", "___"):
            writer.append("---")
            writer.append_paragraph_break()
            i += 1
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            level = min(len(heading_match.group(1)), 3)
            writer.parse_heading_line(line, level)
            i += 1
            continue

        # Blockquote
        if line.startswith("> "):
            writer.parse_blockquote_line(line)
            i += 1
            continue

        # Unordered list
        ul_match = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
        if ul_match:
            indent_spaces = len(ul_match.group(1))
            indent_level = indent_spaces // 2
            writer.parse_list_item(ul_match.group(2), "bullet", indent_level)
            i += 1
            continue

        # Ordered list (markdown - or skill step lines like "1. Deploy...")
        ol_match = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
        if ol_match:
            indent_spaces = len(ol_match.group(1))
            indent_level = indent_spaces // 2
            writer.parse_list_item(ol_match.group(3), "ordered", indent_level)
            i += 1
            continue

        # Plain paragraph (may span until blank line)
        para_lines = [line]
        i += 1
        while i < n:
            next_line = lines[i]
            next_stripped = next_line.strip()
            if not next_stripped:
                break
            if (
                next_stripped.startswith("```")
                or re.match(r"^#{1,6}\s+", next_line)
                or next_line.startswith("> ")
                or re.match(r"^(\s*)[-*+]\s+", next_line)
                or re.match(r"^(\s*)(\d+)\.\s+", next_line)
                or next_stripped in ("---", "***", "___")
            ):
                break
            para_lines.append(next_line)
            i += 1
        writer.parse_plain_paragraph("\n".join(para_lines))

    return writer.blocks


def put_comment(comment_id: str, blocks: list[dict], token: str) -> None:
    url = f"https://api.clickup.com/api/v2/comment/{comment_id}"
    body = json.dumps({"comment": blocks}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=API_TIMEOUT_SEC) as response:
        if response.status not in (200, 201):
            raise urllib.error.HTTPError(
                url, response.status, response.reason, response.headers, None
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upgrade ClickUp comment_text to native rich-text ops."
    )
    parser.add_argument("comment_id", help="ClickUp comment ID from MCP tool response")
    parser.add_argument(
        "comment_text",
        nargs="?",
        default=None,
        help="Plain comment text (omit to read from stdin)",
    )
    args = parser.parse_args()

    token = os.environ.get("CLICKUP_API_TOKEN", "").strip()
    if not token:
        print(
            "clickup_rich_comment: CLICKUP_API_TOKEN is not set. "
            "Export a Personal API Token (pk_...) from ClickUp Settings → Apps.",
            file=sys.stderr,
        )
        return 1

    if args.comment_text is not None:
        raw_text = args.comment_text
    else:
        raw_text = sys.stdin.read()

    if not raw_text.strip():
        print("clickup_rich_comment: empty comment_text, skipping.", file=sys.stderr)
        return 0

    preprocessed = preprocess_plain_text(raw_text)
    blocks = markdown_to_blocks(preprocessed)

    if not blocks:
        print("clickup_rich_comment: no blocks produced, skipping.", file=sys.stderr)
        return 0

    try:
        put_comment(args.comment_id, blocks, token)
    except urllib.error.HTTPError as exc:
        print(
            f"clickup_rich_comment: API error {exc.code}: {exc.reason}",
            file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as exc:
        print(f"clickup_rich_comment: network error: {exc.reason}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
