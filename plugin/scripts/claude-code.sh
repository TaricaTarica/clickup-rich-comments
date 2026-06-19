#!/usr/bin/env bash
# PostToolUse hook for Claude Code plugin: upgrade ClickUp comment_text to rich-text ops.
#
# Requires CLICKUP_API_TOKEN (Personal API Token, pk_...) — in the environment or in
# ~/.clickup_rich_comments.env. The plugin installs the mechanism only — never embed creds.
#
# Configure the matcher to cover both the claude.ai connector and legacy servers:
#   "matcher": "mcp__.*__clickup_create(_task)?_comment"
#
# Parsing is done in clickup_rich_comment.py (--hook), so no jq dependency.
# Fail-open: always exit 0 so the agent session is not blocked.

set -euo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PY="${ROOT}/scripts/clickup_rich_comment.py"
LOG_PREFIX="clickup-rich-comment (claude-code-plugin)"

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

case "$input" in
  *clickup_create*comment*) : ;;
  *) exit 0 ;;
esac

if [[ -z "${SSL_CERT_FILE:-}" ]]; then
  _certifi="$(python3 -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
  if [[ -n "$_certifi" && -f "$_certifi" ]]; then
    export SSL_CERT_FILE="$_certifi"
  fi
fi

if ! printf '%s' "$input" | python3 "$PY" --hook; then
  echo "${LOG_PREFIX}: converter failed; agent flow continues." >&2
fi

exit 0
