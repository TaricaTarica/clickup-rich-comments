#!/usr/bin/env bash
# afterMCPExecution hook for Cursor: upgrade ClickUp comment_text to rich-text ops.
#
# Cursor sends JSON on stdin with:
#   tool_name     — "clickup_create_task_comment" (no MCP prefix)
#   tool_input    — JSON-escaped string; parse with jq 'fromjson'
#   tool_output   — JSON with comment_id
#
# Cursor has no matcher for afterMCPExecution — filter tool_name inside this script.
#
# Fail-open: always exit 0 so the agent session is not blocked.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PREFIX="clickup-rich-comment (cursor)"

if ! command -v jq >/dev/null 2>&1; then
  echo "${LOG_PREFIX}: jq not found; skipping rich-text upgrade." >&2
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

tool_name="$(jq -r '.tool_name // empty' <<<"$input")"
if [[ "$tool_name" != "clickup_create_task_comment" && "$tool_name" != "clickup_create_comment" ]]; then
  exit 0
fi

# tool_input is a JSON string in Cursor — unwrap it
tool_input_raw="$(jq -r '.tool_input // empty' <<<"$input")"
if [[ -z "$tool_input_raw" ]]; then
  echo "${LOG_PREFIX}: empty tool_input; skipping." >&2
  exit 0
fi

comment_text="$(jq -r '.comment_text // empty' <<<"$tool_input_raw")"

# tool_output may be a JSON string or object
tool_output_raw="$(jq -r '.tool_output // empty' <<<"$input")"
if [[ -z "$tool_output_raw" ]]; then
  echo "${LOG_PREFIX}: empty tool_output; skipping." >&2
  exit 0
fi

# Parse tool_output (string or already object)
if jq -e . >/dev/null 2>&1 <<<"$tool_output_raw"; then
  comment_id="$(jq -r '.comment_id // empty' <<<"$tool_output_raw")"
  success="$(jq -r '.success // empty' <<<"$tool_output_raw")"
else
  comment_id=""
  success=""
fi

if [[ "$success" != "true" || -z "$comment_id" ]]; then
  echo "${LOG_PREFIX}: MCP call did not return success/comment_id; skipping." >&2
  exit 0
fi

if [[ -z "$comment_text" ]]; then
  echo "${LOG_PREFIX}: empty comment_text; skipping." >&2
  exit 0
fi

if [[ -z "${SSL_CERT_FILE:-}" ]] && command -v python3 >/dev/null 2>&1; then
  _certifi="$(python3 -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
  if [[ -n "$_certifi" && -f "$_certifi" ]]; then
    export SSL_CERT_FILE="$_certifi"
  fi
fi

if ! python3 "$SCRIPT_DIR/clickup_rich_comment.py" "$comment_id" <<<"$comment_text"; then
  echo "${LOG_PREFIX}: converter failed for comment ${comment_id}; agent flow continues." >&2
fi

exit 0
