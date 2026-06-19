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
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

API_TIMEOUT_SEC = 30
DIVIDER_RE = re.compile(r"^[\u2500\-─]{40,}\s*$")
WARNING_LINES = frozenset({"IMPORTANTE", "OBSOLETO", "MUST", "WARNING", "NOTE"})
URL_RE = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)
LINK_MD_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
# Image markdown: ![alt](ref) — checked before links (the leading ! disambiguates).
IMAGE_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
IMAGE_ONLY_RE = re.compile(r"^!\[[^\]]*\]\([^)]+\)$")
# Markdown table separator row, e.g. |---|:--:|---|
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
DEFAULT_IMAGE_WIDTH = 300


def _split_table_row(line: str) -> list[str]:
    """Split a markdown table row into trimmed cells, dropping leading/trailing pipes."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _ssl_context() -> ssl.SSLContext:
    """Default context, falling back to certifi (python.org builds miss system roots)."""
    try:
        import certifi  # noqa: PLC0415

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # pragma: no cover - certifi optional
        return ssl.create_default_context()


_SSL_CTX = _ssl_context()


def build_image_op(meta: dict, width: int = DEFAULT_IMAGE_WIDTH) -> dict:
    """
    Build a ClickUp `type:image` comment op from a REST attachment-upload response.

    The upload response (POST /task/{id}/attachment) provides every field the inline
    image op needs: id, name/title, extension, thumbnail_*, url, url_w_query, width,
    height. Shape verified against a real ClickUp comment.
    """
    ext = (meta.get("extension") or "png").lstrip(".")
    name = meta.get("name") or meta.get("title") or "image"
    title = meta.get("title") or name
    url = meta.get("url") or meta.get("url_w_host") or ""
    thumb_s = meta.get("thumbnail_small") or url
    thumb_m = meta.get("thumbnail_medium") or url
    thumb_l = meta.get("thumbnail_large") or url

    data_attachment = {
        "id": meta["id"],
        "version": str(meta.get("version", "0")),
        "date": meta.get("date", 0),
        "name": name,
        "title": title,
        "extension": ext,
        "source": meta.get("source", 1),
        "thumbnail_small": thumb_s,
        "thumbnail_medium": thumb_m,
        "thumbnail_large": thumb_l,
        "url": url,
        "url_w_query": meta.get("url_w_query", url),
        "url_w_host": meta.get("url_w_host", url),
    }
    attributes = {
        "width": str(width),
        "data-id": meta["id"],
        "data-attachment": json.dumps(data_attachment, ensure_ascii=False),
    }
    if meta.get("width"):
        attributes["data-natural-width"] = str(meta["width"])
    if meta.get("height"):
        attributes["data-natural-height"] = str(meta["height"])

    return {
        "type": "image",
        "text": urllib.parse.quote(name),
        "image": {
            "id": meta["id"],
            "name": name,
            "title": title,
            "type": ext,
            "extension": f"image/{ext}",
            "thumbnail_large": thumb_l,
            "thumbnail_medium": thumb_m,
            "thumbnail_small": thumb_s,
            "url": url,
            "uploaded": True,
        },
        "attributes": attributes,
    }


def resolve_attachment(ref: str, attachments: dict | None) -> dict | None:
    """Match an image ref (basename or url) against the uploaded-attachment metadata map."""
    if not attachments:
        return None
    if ref in attachments:
        return attachments[ref]
    base = os.path.basename(ref)
    if base in attachments:
        return attachments[base]
    # match by the metadata url
    for meta in attachments.values():
        if ref and ref == meta.get("url"):
            return meta
    return None


class DeltaWriter:
    """
    Emits ClickUp comment ops. Block attributes (header, list, code-block, blockquote)
    ride on the trailing newline for that line; inline attributes ride on text spans.
    Image refs are resolved against `attachments` (filename/url -> upload metadata).
    """

    def __init__(
        self, attachments: dict | None = None, width: int = DEFAULT_IMAGE_WIDTH
    ) -> None:
        self.blocks: list[dict] = []
        self.attachments = attachments or {}
        self.image_width = width

    def append_image(self, alt: str, ref: str) -> bool:
        """Append an inline image op if the ref resolves to an uploaded attachment."""
        meta = resolve_attachment(ref, self.attachments)
        if meta is None:
            return False
        self.blocks.append(build_image_op(meta, self.image_width))
        return True

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

            # Inline image ![alt](ref) — checked before links
            image_match = IMAGE_MD_RE.match(text, pos)
            if image_match:
                alt, ref = image_match.group(1), image_match.group(2)
                if self.append_image(alt, ref):
                    pos = image_match.end()
                    continue
                # Unresolved ref: fall through to render as a plain link
                self.parse_inline(alt or ref, {**attrs, "link": ref})
                pos = image_match.end()
                continue

            # Markdown link [text](url)
            link_match = LINK_MD_RE.match(text, pos)
            if link_match:
                link_text, url = link_match.group(1), link_match.group(2)
                self.parse_inline(link_text, {**attrs, "link": url})
                pos = link_match.end()
                continue

            # Lone '!' that did not start an image marker — emit literally
            if text[pos] == "!":
                self.append("!", attrs)
                pos += 1
                continue

            # Find next special char or URL
            next_special = len(text)
            for marker in ("`", "**", "__", "[", "!"):
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
        # ClickUp requires the nested form: {"list": {"list": "<type>"}}
        attrs: dict = {"list": {"list": list_type}}
        if indent > 0:
            attrs["indent"] = indent
        self.append_paragraph_break(attrs)

    def emit_table(self, header: list[str], rows: list[list[str]]) -> None:
        """ClickUp comments have no table op — render as a bold header line + bullets."""
        if header:
            self.parse_inline(" · ".join(c for c in header if c.strip()), {"bold": True})
            self.append_paragraph_break()
        for row in rows:
            cells = [c for c in row if c.strip()]
            if not cells:
                continue
            self.parse_inline("  —  ".join(cells))
            self.append_paragraph_break({"list": {"list": "bullet"}})

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


def markdown_to_blocks(
    text: str, attachments: dict | None = None, width: int = DEFAULT_IMAGE_WIDTH
) -> list[dict]:
    """Line-based markdown parser → ClickUp comment ops."""
    writer = DeltaWriter(attachments=attachments, width=width)
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

        # Standalone inline image: ![alt](ref) on its own line
        if IMAGE_ONLY_RE.match(stripped):
            m = IMAGE_MD_RE.match(stripped)
            if m and writer.append_image(m.group(1), m.group(2)):
                writer.append_paragraph_break()
                i += 1
                continue

        # Thematic break — ClickUp comments have no divider op; drop it (headers separate
        # sections). Emitting "---" as text renders literally.
        if stripped in ("---", "***", "___"):
            i += 1
            continue

        # Markdown table: a row of cells followed by a |---|---| separator row.
        if "|" in stripped and i + 1 < n and TABLE_SEP_RE.match(lines[i + 1].strip()):
            header = _split_table_row(line)
            i += 2  # consume header + separator
            data_rows: list[list[str]] = []
            while i < n and "|" in lines[i] and lines[i].strip():
                data_rows.append(_split_table_row(lines[i]))
                i += 1
            writer.emit_table(header, data_rows)
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
                or IMAGE_ONLY_RE.match(next_stripped)
            ):
                break
            para_lines.append(next_line)
            i += 1
        writer.parse_plain_paragraph("\n".join(para_lines))

    return writer.blocks


def _api_request(url: str, *, method: str, token: str, data: bytes | None = None,
                 content_type: str | None = None) -> dict:
    headers = {"Authorization": token}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(
        request, timeout=API_TIMEOUT_SEC, context=_SSL_CTX
    ) as response:
        if response.status not in (200, 201):
            raise urllib.error.HTTPError(
                url, response.status, response.reason, response.headers, None
            )
        raw = response.read().decode("utf-8") or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def upload_attachment(task_id: str, file_path: str, token: str) -> dict:
    """POST /task/{id}/attachment as multipart/form-data; return the attachment metadata."""
    url = f"https://api.clickup.com/api/v2/task/{task_id}/attachment"
    boundary = uuid.uuid4().hex
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as fh:
        content = fh.read()
    pre = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="attachment"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    post = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = pre + content + post
    return _api_request(
        url,
        method="POST",
        token=token,
        data=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )


def create_comment(task_id: str, comment_text: str, token: str) -> str:
    """POST /task/{id}/comment (plain text fallback); return the new comment id."""
    url = f"https://api.clickup.com/api/v2/task/{task_id}/comment"
    data = json.dumps({"comment_text": comment_text, "notify_all": False}).encode("utf-8")
    result = _api_request(
        url, method="POST", token=token, data=data, content_type="application/json"
    )
    return str(result.get("id") or "")


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
    with urllib.request.urlopen(
        request, timeout=API_TIMEOUT_SEC, context=_SSL_CTX
    ) as response:
        if response.status not in (200, 201):
            raise urllib.error.HTTPError(
                url, response.status, response.reason, response.headers, None
            )


def _load_attachments_map(path: str | None) -> dict:
    if not path:
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _as_obj(value) -> dict:
    """Accept a dict or a JSON-encoded string; return a dict (empty on failure)."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def extract_from_hook(payload_text: str) -> tuple[str, str]:
    """
    Extract (comment_id, comment_text) from a hook payload, covering both editors:
      Claude Code: tool_input (object) + tool_response (object) with id/comment_id
      Cursor:      tool_input (JSON string) + tool_output (JSON string) with comment_id
    """
    try:
        payload = json.loads(payload_text)
    except (json.JSONDecodeError, ValueError):
        return "", ""
    if not isinstance(payload, dict):
        return "", ""

    tool_input = _as_obj(payload.get("tool_input"))
    comment_text = tool_input.get("comment_text") or ""

    response = _as_obj(payload.get("tool_response") or payload.get("tool_output"))
    comment_id = str(response.get("comment_id") or response.get("id") or "")

    return comment_id, comment_text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upgrade ClickUp comments to native rich-text ops (with inline images)."
    )
    parser.add_argument(
        "comment_id",
        nargs="?",
        default=None,
        help="Existing comment ID to upgrade (hook mode). Omit when using --task.",
    )
    parser.add_argument(
        "comment_text",
        nargs="?",
        default=None,
        help="Plain comment text (omit to read from stdin)",
    )
    parser.add_argument(
        "--task",
        default=None,
        help="Task ID: create the comment, then upgrade it (feature-brief post mode).",
    )
    parser.add_argument(
        "--attach",
        nargs="*",
        default=[],
        help="Image files to upload and render INLINE (matched by basename in ![](ref)).",
    )
    parser.add_argument(
        "--attachments",
        default=None,
        help="JSON file mapping filename/url -> upload metadata (for inline images).",
    )
    parser.add_argument(
        "--width", type=int, default=DEFAULT_IMAGE_WIDTH, help="Inline image width (px)."
    )
    parser.add_argument(
        "--print-ops",
        action="store_true",
        help="Print the resulting ops JSON instead of writing to ClickUp (dry run).",
    )
    parser.add_argument(
        "--hook",
        action="store_true",
        help="Read a PostToolUse/afterMCPExecution payload from stdin (Claude Code & Cursor).",
    )
    args = parser.parse_args()

    # Hook mode: derive comment_id + comment_text from the full hook payload on stdin.
    hook_text: str | None = None
    if args.hook:
        comment_id, hook_text = extract_from_hook(sys.stdin.read())
        if not comment_id or not hook_text.strip():
            print(
                "clickup_rich_comment: hook payload missing comment_id/comment_text; skipping.",
                file=sys.stderr,
            )
            return 0
        args.comment_id = comment_id
        args.comment_text = hook_text

    if not args.comment_id and not args.task and not args.print_ops:
        parser.error("provide a comment_id (hook mode) or --task (post mode)")

    token = os.environ.get("CLICKUP_API_TOKEN", "").strip()
    if not token and not args.print_ops:
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

    # Build the attachments metadata map: from --attachments file and/or by uploading --attach.
    attachments = _load_attachments_map(args.attachments)
    try:
        for file_path in args.attach:
            meta = upload_attachment(args.task, file_path, token)
            attachments[os.path.basename(file_path)] = meta
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        print(f"clickup_rich_comment: attachment upload failed: {exc}", file=sys.stderr)
        return 1

    preprocessed = preprocess_plain_text(raw_text)
    blocks = markdown_to_blocks(preprocessed, attachments=attachments, width=args.width)

    if not blocks:
        print("clickup_rich_comment: no blocks produced, skipping.", file=sys.stderr)
        return 0

    if args.print_ops:
        print(json.dumps(blocks, indent=2, ensure_ascii=False))
        return 0

    comment_id = args.comment_id
    try:
        if not comment_id:
            # Post mode: create a plain comment first, then upgrade it.
            comment_id = create_comment(args.task, raw_text, token)
            if not comment_id:
                print("clickup_rich_comment: failed to create comment.", file=sys.stderr)
                return 1
        put_comment(comment_id, blocks, token)
    except urllib.error.HTTPError as exc:
        print(
            f"clickup_rich_comment: API error {exc.code}: {exc.reason}",
            file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as exc:
        print(f"clickup_rich_comment: network error: {exc.reason}", file=sys.stderr)
        return 1

    if args.task:
        print(json.dumps({
            "comment_id": comment_id,
            "attachments": {k: v.get("url") for k, v in attachments.items()},
        }, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
