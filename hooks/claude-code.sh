#!/usr/bin/env bash
# PostToolUse hook for Claude Code: upgrade ClickUp comment_text to rich-text ops.
#
# Claude Code sends JSON on stdin with:
#   tool_input.comment_text  — plain string
#   tool_response.comment_id — from clickup_create_task_comment
#
# Configure in ~/.claude/settings.json with a matcher like:
#   "matcher": "mcp__<server>__clickup_create_task_comment"
#
# Fail-open: always exit 0 so the agent session is not blocked.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PREFIX="clickup-rich-comment (claude-code)"

if ! command -v jq >/dev/null 2>&1; then
  echo "${LOG_PREFIX}: jq not found; skipping rich-text upgrade." >&2
  exit 0
fi

if [[ -z "${CLICKUP_API_TOKEN:-}" ]]; then
  echo "${LOG_PREFIX}: CLICKUP_API_TOKEN not set; skipping rich-text upgrade." >&2
  exit 0
fi

input="$(cat)"

success="$(jq -r '.tool_response.success // empty' <<<"$input")"
if [[ "$success" != "true" ]]; then
  exit 0
fi

comment_id="$(jq -r '.tool_response.comment_id // empty' <<<"$input")"
comment_text="$(jq -r '.tool_input.comment_text // empty' <<<"$input")"

if [[ -z "$comment_id" || -z "$comment_text" ]]; then
  echo "${LOG_PREFIX}: missing comment_id or comment_text in hook payload; skipping." >&2
  exit 0
fi

if ! python3 "$SCRIPT_DIR/clickup_rich_comment.py" "$comment_id" <<<"$comment_text"; then
  echo "${LOG_PREFIX}: converter failed for comment ${comment_id}; agent flow continues." >&2
fi

exit 0
