#!/usr/bin/env bash
# PostToolUse hook for Claude Code plugin: upgrade ClickUp comment_text to rich-text ops.
#
# Requires CLICKUP_API_TOKEN in the environment (Personal API Token, pk_...).
# The plugin installs the mechanism only — never embed credentials.
#
# Claude Code sends JSON on stdin with:
#   tool_input.comment_text  — plain string
#   tool_response.comment_id — from clickup_create_task_comment
#
# Paths use ${CLAUDE_PLUGIN_ROOT} when invoked by the plugin runtime; falls back to
# resolving this script's plugin directory for local testing.
#
# Fail-open: always exit 0 so the agent session is not blocked.

set -euo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PY="${ROOT}/scripts/clickup_rich_comment.py"
LOG_PREFIX="clickup-rich-comment (claude-code-plugin)"

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

if ! python3 "$PY" "$comment_id" <<<"$comment_text"; then
  echo "${LOG_PREFIX}: converter failed for comment ${comment_id}; agent flow continues." >&2
fi

exit 0
