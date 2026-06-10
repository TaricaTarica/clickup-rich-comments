#!/usr/bin/env bash
# Temporary diagnostic hook for Cursor — discover the real MCP tool_name and payload shape.
#
# Usage:
#   1. Point ~/.cursor/hooks.json afterMCPExecution to this script (absolute path).
#   2. Ask the agent to create a ClickUp comment via MCP.
#   3. Read ~/.cursor/clickup-mcp-debug.log
#   4. Remove this hook once you have the tool_name for Claude Code matcher config.
#
# Always exits 0 (fail-open).

set -euo pipefail

LOG_FILE="${HOME}/.cursor/clickup-mcp-debug.log"
timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
input="$(cat)"

{
  echo "=== ${timestamp} ==="
  if command -v jq >/dev/null 2>&1; then
    echo "tool_name: $(jq -r '.tool_name // "MISSING"' <<<"$input")"
    echo "tool_input (first 500 chars): $(jq -r '.tool_input // ""' <<<"$input" | head -c 500)"
    echo "tool_output (first 500 chars): $(jq -r '.tool_output // ""' <<<"$input" | head -c 500)"
  else
    echo "jq not found — raw stdin (first 1000 chars):"
    head -c 1000 <<<"$input"
  fi
  echo ""
} >>"$LOG_FILE"

exit 0
