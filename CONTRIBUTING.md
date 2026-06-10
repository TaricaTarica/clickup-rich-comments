# Contributing

Thanks for helping improve clickup-comment-style. The core feature is the **hook + converter** that upgrades ClickUp MCP comments to rich text. The optional style guide (`SKILL.md`) is secondary.

## Extending the converter (core)

All converter logic lives in [`hooks/clickup_rich_comment.py`](hooks/clickup_rich_comment.py). Stdlib only — no pip dependencies.

### Preprocessor (`preprocess_plain_text`)

Maps the plain-text dialect to pseudo-markdown before the block parser runs:

| Plain-text convention | Pseudo-markdown |
|-----------------------|-----------------|
| `────────────────...` (40+ chars) | `---` |
| Numbered title between dividers | `## Title` |
| `• ` bullet | `- ` bullet |
| `– ` sub-bullet | nested `- ` |
| 4-space indent block | fenced code |
| `IMPORTANTE` / `MUST` alone | `**IMPORTANTE**` |

To add a new convention: edit `preprocess_plain_text()`, add a test fixture, run the snippet below.

### Parser (`markdown_to_blocks` / `DeltaWriter`)

ClickUp ops model ([official docs](https://developer.clickup.com/docs/comment-formatting)):

- **Block attrs** on trailing `\n`: `header`, `list`, `indent`, `code-block`, `blockquote`
- **Inline attrs** on text spans: `bold`, `italic`, `underline`, `code`, `link`

Reference: [clickup-cli markdown → delta blocks](https://github.com/triptechtravel/clickup-cli).

### Test a fixture locally

```bash
python3 -c "
import sys
sys.path.insert(0, 'hooks')
from clickup_rich_comment import preprocess_plain_text, markdown_to_blocks
import json
text = open('your-fixture.txt').read()
blocks = markdown_to_blocks(preprocess_plain_text(text))
print(json.dumps(blocks, indent=2))
"
```

Or test the full PUT path:

```bash
export CLICKUP_API_TOKEN=pk_...
python3 hooks/clickup_rich_comment.py '<comment_id>' < your-fixture.txt
```

## Testing end-to-end

1. `export CLICKUP_API_TOKEN=pk_...`
2. Run `./install.sh` or configure hooks manually.
3. Create a comment via MCP (agent or tool call).
4. Confirm hook logs on stderr if token/jq missing (must not block agent — exit 0).
5. Open the task in ClickUp — verify headers, lists, code blocks.
6. Optional: GET comment via API and inspect the `comment` ops array.

## Hook wrappers

[`hooks/cursor.sh`](hooks/cursor.sh) and [`hooks/claude-code.sh`](hooks/claude-code.sh) must always **fail open** (`exit 0` on errors). Never block the agent session.

When changing wrapper logic, test with mock stdin:

```bash
echo '{"tool_name":"clickup_create_task_comment","tool_input":"{\"comment_text\":\"## test\"}","tool_output":"{\"success\":true,\"comment_id\":\"123\"}"}' \
  | CLICKUP_API_TOKEN=pk_test ./hooks/cursor.sh
```

## Installer (`install.sh`)

Keep idempotent: re-running must not duplicate hook entries.

- **Cursor:** inline Python merge in `install.sh` checks for existing `command` in `~/.cursor/hooks.json`.
- **Claude Code:** [`scripts/merge_claude_hooks.py`](scripts/merge_claude_hooks.py) merges into `~/.claude/settings.json`, preserving other keys (`enabledPlugins`, `theme`, etc.).

Test Claude merge idempotency:

```bash
python3 scripts/merge_claude_hooks.py /tmp/test-settings.json "$(pwd)/hooks/claude-code.sh"
python3 scripts/merge_claude_hooks.py /tmp/test-settings.json "$(pwd)/hooks/claude-code.sh"
# second run → already_installed
```

Confirm prompts before modifying user files (`~/.zshrc`, `~/.cursor/hooks.json`, `~/.claude/settings.json`).

## Optional: agent style guide

To add a comment archetype (few-shot):

1. Add template under **Templates by type** in [`SKILL.md`](SKILL.md).
2. Add anonymized few-shot (placeholders: `acme-connector`, `ORG-123`, `example.com`).
3. Mirror in [`.cursor/rules/clickup-comment-style.mdc`](.cursor/rules/clickup-comment-style.mdc).
4. Verify with and without the hook.

## Pull requests

- Keep `clickup_rich_comment.py` stdlib-only.
- Hook wrappers must fail open.
- Anonymize few-shots — no real client names, internal URLs, or production IDs.
- Test `install.sh` on macOS bash (3.2) — avoid bash 4+ syntax like `${var,,}`.
