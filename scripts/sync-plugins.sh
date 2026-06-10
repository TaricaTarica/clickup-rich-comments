#!/usr/bin/env bash
# Provision symlinks for plugin/ (Claude Code) and plugin-cursor/ (Cursor) from repo-root sources.
# Does not copy editable files — run after clone if symlinks are missing (e.g. Windows without symlink support).
#
# Usage: ./scripts/sync-plugins.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

link() {
  local target="$1"
  local link_path="$2"
  mkdir -p "$(dirname "$link_path")"
  if [[ -L "$link_path" && "$(readlink "$link_path")" == "$target" ]]; then
    return 0
  fi
  if [[ -e "$link_path" && ! -L "$link_path" ]]; then
    echo "error: $link_path exists and is not a symlink" >&2
    exit 1
  fi
  ln -sf "$target" "$link_path"
}

echo "Syncing plugin symlinks in ${REPO_ROOT}..."

# ── Claude Code plugin (plugin/) ─────────────────────────────────────────────
link "../SKILL.md" \
  "${REPO_ROOT}/plugin/SKILL.md"
link "../../hooks/clickup_rich_comment.py" \
  "${REPO_ROOT}/plugin/scripts/clickup_rich_comment.py"

# ── Cursor plugin (plugin-cursor/) ───────────────────────────────────────────
link "../../../SKILL.md" \
  "${REPO_ROOT}/plugin-cursor/skills/clickup-comment-style/SKILL.md"
link "../../.cursor/rules/clickup-comment-style.mdc" \
  "${REPO_ROOT}/plugin-cursor/rules/clickup-comment-style.mdc"
link "../../hooks/clickup_rich_comment.py" \
  "${REPO_ROOT}/plugin-cursor/scripts/clickup_rich_comment.py"
link "../../hooks/cursor.sh" \
  "${REPO_ROOT}/plugin-cursor/scripts/cursor.sh"

chmod +x "${REPO_ROOT}/hooks/cursor.sh" \
  "${REPO_ROOT}/hooks/claude-code.sh" \
  "${REPO_ROOT}/plugin/scripts/claude-code.sh" 2>/dev/null || true
if [[ -L "${REPO_ROOT}/plugin-cursor/scripts/cursor.sh" ]]; then
  chmod +x "${REPO_ROOT}/plugin-cursor/scripts/cursor.sh"
fi

echo "Done. Symlinks:"
ls -la "${REPO_ROOT}/plugin/" "${REPO_ROOT}/plugin/scripts/" 2>/dev/null || true
ls -la "${REPO_ROOT}/plugin-cursor/skills/clickup-comment-style/" \
       "${REPO_ROOT}/plugin-cursor/rules/" \
       "${REPO_ROOT}/plugin-cursor/scripts/" 2>/dev/null || true
