#!/usr/bin/env bash
# PostToolUse hook for Claude Code: upgrade ClickUp comment_text to rich-text ops.
#
# Claude Code sends JSON on stdin with:
#   tool_name      — e.g. "mcp__claude_ai_ClickUp__clickup_create_comment"
#   tool_input     — object (or JSON string) with comment_text
#   tool_response  — object (or JSON string) with the created comment (id / comment_id)
#
# Configure in ~/.claude/settings.json with a regex matcher that covers both the
# claude.ai connector (clickup_create_comment) and legacy servers (clickup_create_task_comment):
#   "matcher": "mcp__.*__clickup_create(_task)?_comment"
#
# Parsing is done in clickup_rich_comment.py (--hook), so no jq dependency.
# Fail-open: always exit 0 so the agent session is not blocked.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PREFIX="clickup-rich-comment (claude-code)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "${LOG_PREFIX}: python3 not found; skipping rich-text upgrade." >&2
  exit 0
fi

# Load CLICKUP_API_TOKEN from the env file if not already exported (Claude Code hooks
# do not inherit an interactive shell's profile).
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

# Optional debug: dump the raw hook payload to inspect the connector's field shape.
if [[ -n "${CLICKUP_RICH_COMMENTS_DEBUG:-}" ]]; then
  printf '%s\n' "$input" \
    >>"${CLICKUP_RICH_COMMENTS_DEBUG_LOG:-$HOME/.clickup_rich_comments.debug.log}" 2>/dev/null || true
fi

# Cheap guard: only spend a python process on ClickUp comment-create payloads.
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
