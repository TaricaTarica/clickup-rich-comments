#!/usr/bin/env bash
# afterMCPExecution hook for Cursor: upgrade ClickUp comment_text to rich-text ops.
#
# Cursor sends JSON on stdin with:
#   tool_name     — "clickup_create_comment" / "clickup_create_task_comment" (no MCP prefix)
#   tool_input    — JSON-escaped string with comment_text
#   tool_output   — JSON (string or object) with comment_id / id
#
# Cursor has no matcher for afterMCPExecution — filter inside this script.
# Parsing is done in clickup_rich_comment.py (--hook), so no jq dependency.
#
# Fail-open: always exit 0 so the agent session is not blocked.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PREFIX="clickup-rich-comment (cursor)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "${LOG_PREFIX}: python3 not found; skipping rich-text upgrade." >&2
  exit 0
fi

ENV_FILE="${CLICKUP_RICH_COMMENTS_ENV:-$HOME/.clickup_rich_comments.env}"
if [[ -z "${CLICKUP_API_TOKEN:-}" && -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${CLICKUP_API_TOKEN:-}" ]]; then
  echo "${LOG_PREFIX}: CLICKUP_API_TOKEN not set; skipping rich-text upgrade." >&2
  exit 0
fi

input="$(cat)"

if [[ -n "${CLICKUP_RICH_COMMENTS_DEBUG:-}" ]]; then
  printf '%s\n' "$input" \
    >>"${CLICKUP_RICH_COMMENTS_DEBUG_LOG:-$HOME/.clickup_rich_comments.debug.log}" 2>/dev/null || true
fi

# afterMCPExecution fires for every MCP tool — only act on ClickUp comment creation.
case "$input" in
  *clickup_create*comment*) : ;;
  *) exit 0 ;;
esac

# python.org builds miss system roots — point urllib at certifi if available.
if [[ -z "${SSL_CERT_FILE:-}" ]]; then
  _certifi="$(python3 -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
  if [[ -n "$_certifi" && -f "$_certifi" ]]; then
    export SSL_CERT_FILE="$_certifi"
  fi
fi

if ! printf '%s' "$input" | python3 "$SCRIPT_DIR/clickup_rich_comment.py" --hook; then
  echo "${LOG_PREFIX}: converter failed; agent flow continues." >&2
fi

exit 0
