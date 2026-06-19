#!/usr/bin/env bash
# Interactive installer for clickup-comment-style hooks.
# Upgrades ClickUp MCP comments from plain comment_text to native rich-text ops.
#
# Usage: ./install.sh
# Idempotent — safe to re-run.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURSOR_HOOK="$REPO_ROOT/hooks/cursor.sh"
CLAUDE_HOOK="$REPO_ROOT/hooks/claude-code.sh"
CURSOR_HOOKS_JSON="${HOME}/.cursor/hooks.json"
CLAUDE_SETTINGS="${HOME}/.claude/settings.json"

# Colors (no external deps)
if [[ -t 1 ]]; then
  BOLD='\033[1m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  RED='\033[0;31m'
  CYAN='\033[0;36m'
  RESET='\033[0m'
else
  BOLD='' GREEN='' YELLOW='' RED='' CYAN='' RESET=''
fi

info()  { echo -e "${CYAN}→${RESET} $*"; }
ok()    { echo -e "${GREEN}✓${RESET} $*"; }
warn()  { echo -e "${YELLOW}!${RESET} $*"; }
err()   { echo -e "${RED}✗${RESET} $*" >&2; }

confirm() {
  local prompt="$1"
  local reply
  read -r -p "$(echo -e "${YELLOW}?${RESET} ${prompt} [y/N] ")" reply
  reply="$(echo "$reply" | tr '[:upper:]' '[:lower:]')"
  [[ "$reply" == "y" || "$reply" == "yes" ]]
}

shell_profile() {
  case "${SHELL:-/bin/bash}" in
    */zsh)  echo "${HOME}/.zshrc" ;;
    */bash) echo "${HOME}/.bashrc" ;;
    *)      echo "${HOME}/.profile" ;;
  esac
}

echo ""
echo -e "${BOLD}clickup-comment-style installer${RESET}"
echo "Transparent Markdown upgrade for the ClickUp MCP."
echo ""

# ── 1. Prerequisites ──────────────────────────────────────────────────────────
info "Checking prerequisites..."

missing=0
if command -v python3 >/dev/null 2>&1; then
  ok "python3 found ($(python3 --version 2>&1))"
else
  err "python3 not found. Install Python 3 and re-run."
  missing=1
fi

if command -v jq >/dev/null 2>&1; then
  ok "jq found"
else
  warn "jq not found — hooks will skip rich-text upgrade until jq is installed."
  warn "  macOS: brew install jq"
  warn "  Linux: apt install jq / yum install jq"
fi

if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

# ── 2. CLICKUP_API_TOKEN ──────────────────────────────────────────────────────
info "Setting up CLICKUP_API_TOKEN..."

if [[ -n "${CLICKUP_API_TOKEN:-}" ]]; then
  ok "CLICKUP_API_TOKEN is already set in this shell."
else
  echo ""
  echo "  The ClickUp MCP OAuth token is not accessible to local hooks."
  echo "  You need a Personal API Token (pk_...) from ClickUp:"
  echo ""
  echo "    1. Open ClickUp → click your avatar → Settings"
  echo "    2. Go to the Apps tab"
  echo "    3. Under API Token, click Generate or Copy"
  echo "    4. Paste the token below (starts with pk_)"
  echo ""

  token=""
  while true; do
    read -r -s -p "  Paste your ClickUp API token (pk_...): " token
    echo ""
    if [[ -z "$token" ]]; then
      warn "Token cannot be empty."
      continue
    fi
    if [[ ! "$token" =~ ^pk_ ]]; then
      warn "Token should start with pk_. Check you copied the Personal API Token."
      if ! confirm "Use this token anyway?"; then
        continue
      fi
    fi
    break
  done

  export CLICKUP_API_TOKEN="$token"
  ok "Token accepted for this session."

  PROFILE="$(shell_profile)"
  export_line="export CLICKUP_API_TOKEN='${token}'"

  if [[ -f "$PROFILE" ]] && grep -q "CLICKUP_API_TOKEN" "$PROFILE" 2>/dev/null; then
    ok "CLICKUP_API_TOKEN already referenced in ${PROFILE}"
  elif confirm "Save CLICKUP_API_TOKEN to ${PROFILE} (persists across sessions)?"; then
    echo "" >>"$PROFILE"
    echo "# clickup-comment-style — rich-text comment upgrade" >>"$PROFILE"
    echo "$export_line" >>"$PROFILE"
    ok "Added to ${PROFILE}"
    warn "Run: source ${PROFILE}   (or open a new terminal)"
  else
    warn "Token not saved. Export manually before each session:"
    echo "  export CLICKUP_API_TOKEN='pk_...'"
  fi
fi

# ── 3. Make scripts executable ────────────────────────────────────────────────
info "Making scripts executable..."
chmod +x "$REPO_ROOT/hooks/"*.sh "$REPO_ROOT/hooks/clickup_rich_comment.py" \
         "$REPO_ROOT/scripts/"*.sh "$REPO_ROOT/scripts/"*.py 2>/dev/null || true
ok "Scripts are executable."

# ── 4. Detect IDE ─────────────────────────────────────────────────────────────
info "Detecting IDE environment..."

has_cursor=0
has_claude=0
if [[ -d "${HOME}/.cursor" ]]; then has_cursor=1; fi
if [[ -d "${HOME}/.claude" ]]; then has_claude=1; fi

setup_cursor=0
setup_claude=0

if [[ "$has_cursor" -eq 1 && "$has_claude" -eq 1 ]]; then
  echo ""
  echo "  Both Cursor and Claude Code detected."
  if confirm "Install Cursor hook (~/.cursor/hooks.json)?"; then setup_cursor=1; fi
  if confirm "Install Claude Code hook (~/.claude/settings.json)?"; then setup_claude=1; fi
elif [[ "$has_cursor" -eq 1 ]]; then
  setup_cursor=1
  ok "Cursor detected."
elif [[ "$has_claude" -eq 1 ]]; then
  setup_claude=1
  ok "Claude Code detected."
else
  warn "Neither ~/.cursor nor ~/.claude found."
  if confirm "Install Cursor hook anyway?"; then setup_cursor=1; fi
  if confirm "Install Claude Code hook (~/.claude/settings.json)?"; then setup_claude=1; fi
fi

# ── 5a. Cursor hooks.json merge ───────────────────────────────────────────────
if [[ "$setup_cursor" -eq 1 ]]; then
  info "Configuring Cursor hook..."

  merge_result="$(python3 - "$CURSOR_HOOKS_JSON" "$CURSOR_HOOK" <<'PY'
import json, os, sys
hooks_path = sys.argv[1]
hook_cmd   = sys.argv[2]
entry = {"command": hook_cmd}
if os.path.isfile(hooks_path):
    with open(hooks_path) as f:
        data = json.load(f)
else:
    data = {"version": 1, "hooks": {}}
hooks = data.setdefault("hooks", {})
after = hooks.setdefault("afterMCPExecution", [])
if any(e.get("command") == hook_cmd for e in after):
    print("already_installed")
    sys.exit(0)
after.append(entry)
os.makedirs(os.path.dirname(hooks_path), exist_ok=True)
with open(hooks_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print("installed")
PY
)"

  if [[ "$merge_result" == "already_installed" ]]; then
    ok "Cursor hook already registered in ${CURSOR_HOOKS_JSON}"
  else
    ok "Cursor hook added to ${CURSOR_HOOKS_JSON}"
    warn "Restart Cursor (or save hooks.json triggers reload) for the hook to activate."
  fi
fi

# ── 5b. Claude Code settings.json merge ───────────────────────────────────────
if [[ "$setup_claude" -eq 1 ]]; then
  info "Configuring Claude Code hook..."

  DEFAULT_MATCHER="mcp__.*__clickup_create(_task)?_comment"
  suggested="$(python3 "$REPO_ROOT/scripts/merge_claude_hooks.py" --suggest-matcher)"
  matcher="$DEFAULT_MATCHER"

  if [[ -n "$suggested" && "$suggested" != "$DEFAULT_MATCHER" ]]; then
    echo ""
    echo "  Detected matcher hint: ${suggested}"
    echo "  (from local MCP config or debug log — may differ from Claude Code tool names)"
    if confirm "Use this exact matcher instead of regex ${DEFAULT_MATCHER}?"; then
      matcher="$suggested"
    else
      ok "Using regex matcher: ${DEFAULT_MATCHER}"
    fi
  fi

  merge_result="$(python3 "$REPO_ROOT/scripts/merge_claude_hooks.py" \
    "$CLAUDE_SETTINGS" "$CLAUDE_HOOK" --matcher "$matcher")"

  if [[ "$merge_result" == "already_installed" ]]; then
    ok "Claude Code hook already registered in ${CLAUDE_SETTINGS}"
  elif [[ "$merge_result" == "installed" ]]; then
    ok "Claude Code hook added to ${CLAUDE_SETTINGS} (matcher: ${matcher})"
    warn "Restart your Claude Code session for the hook to activate."
  else
    err "Failed to merge Claude Code settings: ${merge_result}"
  fi
fi

# ── 6. Verification ───────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Setup complete${RESET}"
echo ""
echo "  Verify your token:"
echo "    echo \$CLICKUP_API_TOKEN"
echo ""
echo "  Test the converter manually (replace COMMENT_ID):"
echo "    python3 ${REPO_ROOT}/hooks/clickup_rich_comment.py COMMENT_ID <<'EOF'"
echo "    ## Test"
echo "    - \`foo()\` — does something"
echo "    ref: https://example.com/docs"
echo "    EOF"
echo ""
echo "  End-to-end: ask your agent to post a ClickUp comment via MCP,"
echo "  then check the task in ClickUp — headers, lists, and code should render."
echo ""
echo "  Optional: install the agent style guide (SKILL.md) — see README."
echo ""
