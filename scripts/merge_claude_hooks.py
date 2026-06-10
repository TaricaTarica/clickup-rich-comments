#!/usr/bin/env python3
"""
Merge a PostToolUse hook into Claude Code settings.json (idempotent).

Usage:
  merge_claude_hooks.py <settings_path> <hook_command> [--matcher PATTERN]
  merge_claude_hooks.py --suggest-matcher

Prints: installed | already_installed | error: ...
Exit 0 on success, 1 on error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_MATCHER = "mcp__.*__clickup_create_task_comment"
TOOL_SUFFIX = "clickup_create_task_comment"


def detect_clickup_matcher() -> str | None:
    """
    Try to infer an exact matcher from local MCP config or debug log.
    Returns None if no hint found.
    """
    home = Path.home()

    mcp_json = home / ".cursor" / "mcp.json"
    if mcp_json.is_file():
        try:
            data = json.loads(mcp_json.read_text())
            servers = data.get("mcpServers", {})
            for name, cfg in servers.items():
                url = str(cfg.get("url", "")).lower()
                if "clickup" in url or "clickup" in name.lower():
                    return f"mcp__{name}__{TOOL_SUFFIX}"
        except (json.JSONDecodeError, OSError):
            pass

    debug_log = home / ".cursor" / "clickup-mcp-debug.log"
    if debug_log.is_file():
        try:
            text = debug_log.read_text()
            match = re.search(r"mcp__[^\s]+__" + TOOL_SUFFIX, text)
            if match:
                return match.group(0)
        except OSError:
            pass

    return None


def hook_already_installed(post_tool_use: list, hook_command: str) -> bool:
    for entry in post_tool_use:
        for hook in entry.get("hooks", []):
            if hook.get("command") == hook_command:
                return True
    return False


def merge_settings(
    settings_path: str,
    hook_command: str,
    matcher: str,
) -> str:
    path = Path(settings_path)

    if path.is_file():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            return f"error: invalid JSON in {settings_path}: {exc}"
    else:
        data = {}

    hooks = data.setdefault("hooks", {})
    post_tool_use = hooks.setdefault("PostToolUse", [])

    if hook_already_installed(post_tool_use, hook_command):
        return "already_installed"

    post_tool_use.append(
        {
            "matcher": matcher,
            "hooks": [
                {
                    "type": "command",
                    "command": hook_command,
                    "async": True,
                }
            ],
        }
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return "installed"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge ClickUp rich-comment PostToolUse hook into Claude Code settings."
    )
    parser.add_argument(
        "settings_path",
        nargs="?",
        help="Path to settings.json (e.g. ~/.claude/settings.json)",
    )
    parser.add_argument(
        "hook_command",
        nargs="?",
        help="Absolute path to claude-code.sh",
    )
    parser.add_argument(
        "--matcher",
        default=DEFAULT_MATCHER,
        help=f"PostToolUse matcher (default: {DEFAULT_MATCHER})",
    )
    parser.add_argument(
        "--suggest-matcher",
        action="store_true",
        help="Print detected exact matcher hint and exit",
    )
    args = parser.parse_args()

    if args.suggest_matcher:
        hint = detect_clickup_matcher()
        if hint:
            print(hint)
        else:
            print(DEFAULT_MATCHER)
        return 0

    if not args.settings_path or not args.hook_command:
        parser.error("settings_path and hook_command are required unless --suggest-matcher")

    result = merge_settings(args.settings_path, args.hook_command, args.matcher)
    print(result)
    return 0 if result in ("installed", "already_installed") else 1


if __name__ == "__main__":
    sys.exit(main())
