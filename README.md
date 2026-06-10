# clickup-comment-style

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3](https://img.shields.io/badge/python-3-3776ab.svg)](hooks/clickup_rich_comment.py)

**Transparent Markdown upgrade for the ClickUp MCP** — works with Cursor and Claude Code.

The ClickUp MCP (`clickup_create_task_comment`) only writes `comment_text` as plain text. Headers, bold, lists, and code blocks appear **literal** in the UI. This project adds a post-hook that upgrades each new comment to ClickUp's native rich-text format automatically — no workflow changes for you or your agent.

## Quickstart

```bash
git clone https://github.com/YOUR_USER/clickup-comment-style.git
cd clickup-comment-style
./install.sh
```

The installer checks prerequisites, guides you through `CLICKUP_API_TOKEN` setup, and configures hooks for Cursor and Claude Code automatically. Takes about two minutes.

**Requirements:** `python3`, `jq` (for hook wrappers). No pip packages.

---

## How it works

```
Agent calls clickup_create_task_comment (MCP)
    → comment_text posted (partial render: backticks + URLs only)

Post-hook fires automatically (claude-code.sh / cursor.sh)
    → clickup_rich_comment.py converts text → ClickUp ops
    → PUT /api/v2/comment/{comment_id} with {"comment": [...]}

ClickUp UI shows full rich text (headers, bold, lists, code blocks)
```

The MCP OAuth token is **not** accessible to local hooks. The upgrade uses a **Personal API Token** (`pk_...`) via `CLICKUP_API_TOKEN`.

### What `comment_text` renders without the hook

| In `comment_text` | Renders in ClickUp UI? |
|-------------------|------------------------|
| Inline code `` `identifier` `` | Yes |
| Raw URL `https://...` | Yes (auto-link) |
| `**bold**`, `*italic*`, `~~strike~~` | No — literal |
| `[text](url)` | No — literal |
| `##` headers, `-` bullets, `1.` lists | No — literal |
| `>` blockquote, ` ``` ` fences | No — literal |

Native formatting lives in the `comment` field (Quill-delta ops array). The MCP does not expose it. See [ClickUp comment formatting](https://developer.clickup.com/docs/comment-formatting).

---

## Step-by-step: get your CLICKUP_API_TOKEN

The installer handles this interactively, but here is the full manual path:

### 1. Open ClickUp Settings

Click your **avatar** (bottom-left) → **Settings**.

### 2. Copy your Personal API Token

Go to the **Apps** tab. Under **API Token**, click **Generate** (or **Copy** if you already have one).

The token starts with `pk_`.

### 3. Export for the current session

```bash
export CLICKUP_API_TOKEN='pk_...'
```

### 4. Persist across sessions

Add to your shell profile so every terminal (and IDE hook process) has the token:

**zsh** (`~/.zshrc`):

```bash
echo 'export CLICKUP_API_TOKEN='"'"'pk_...'"'" >> ~/.zshrc
source ~/.zshrc
```

**bash** (`~/.bashrc`):

```bash
echo 'export CLICKUP_API_TOKEN='"'"'pk_...'"'" >> ~/.bashrc
source ~/.bashrc
```

### 5. Verify

```bash
echo $CLICKUP_API_TOKEN
# should print: pk_...
```

> Never commit your token. Use environment variables or your shell profile — not a `.env` file in a repo.

---

## Install as a Claude Code plugin (recommended for Claude Code users)

For Claude Code, install the hook and style guide in one step via the plugin marketplace:

```bash
claude plugin marketplace add TaricaTarica/clickup-rich-comments
```

Then in a Claude Code session:

```
/plugin install clickup-comment-style@clickup-rich-comments
```

After install, restart the session or run `/reload-plugins`. Hook changes are not hot-reloaded; `SKILL.md` updates are.

**Requirements:** `python3`, `jq`, and `CLICKUP_API_TOKEN` in your environment (see above). The plugin installs the mechanism only — it never embeds or ships credentials.

**What you get:** a `PostToolUse` hook that upgrades `clickup_create_task_comment` output to native rich text, plus the comment style guide skill.

**ClickUp MCP:** must already be configured separately (OAuth). This plugin does not declare `.mcp.json` — adding ClickUp MCP again would conflict with your existing setup.

**Cursor users:** Claude Code plugins are not consumed by Cursor. Use [`./install.sh`](#quickstart) or the [manual Cursor setup](#cursor) below.

**Avoid double hooks:** if you install via the plugin, do not also merge the hook into `~/.claude/settings.json` via `./install.sh` — you would run the upgrade twice per comment.

**Marketplace source:** add the marketplace via Git shorthand (`owner/repo`) or a git URL. Do not add it via a direct URL to `marketplace.json` — relative plugin paths (`./plugin`) only resolve when the marketplace is fetched from a git repository.

---

## Manual setup (without install.sh)

### Cursor

Merge into `~/.cursor/hooks.json` (see [`config-examples/cursor-hooks.json`](config-examples/cursor-hooks.json)):

```json
{
  "version": 1,
  "hooks": {
    "afterMCPExecution": [
      {
        "command": "/ABSOLUTE/PATH/to/clickup-comment-style/hooks/cursor.sh"
      }
    ]
  }
}
```

```bash
chmod +x hooks/*.sh scripts/*.sh
```

| Field | Cursor |
|-------|--------|
| Event | `afterMCPExecution` |
| Config | `~/.cursor/hooks.json` |
| Matcher | No — `cursor.sh` filters `tool_name` internally |
| `tool_name` | `clickup_create_task_comment` (no MCP prefix) |
| `tool_input` | JSON string — unwrap with `jq 'fromjson'` |
| Comment ID | `tool_output.comment_id` |
| Async | Not documented (runs synchronously) |

Restart Cursor or save `hooks.json` to reload hooks.

### Claude Code

`./install.sh` merges the hook into `~/.claude/settings.json` automatically (with confirmation). Matcher default: regex `mcp__.*__clickup_create_task_comment` — works across MCP server naming (e.g. `mcp__claude_ai_ClickUp__clickup_create_task_comment`) without manual configuration.

Manual merge (see [`config-examples/claude-settings.json`](config-examples/claude-settings.json)):

```bash
python3 scripts/merge_claude_hooks.py ~/.claude/settings.json "$(pwd)/hooks/claude-code.sh"
```

Or merge JSON by hand:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "mcp__.*__clickup_create_task_comment",
        "hooks": [
          {
            "type": "command",
            "command": "/ABSOLUTE/PATH/to/clickup-comment-style/hooks/claude-code.sh",
            "async": true
          }
        ]
      }
    ]
  }
}
```

Restart your Claude Code session after install.

| Field | Claude Code |
|-------|-------------|
| Event | `PostToolUse` |
| Config | `~/.claude/settings.json` |
| Matcher | Regex `mcp__.*__clickup_create_task_comment` (no server name needed) |
| `tool_input` | JSON object |
| Comment ID | `tool_response.comment_id` |
| Async | Supported (`"async": true`) |

---

## Verify it works

### Test the converter directly

```bash
export CLICKUP_API_TOKEN='pk_...'
python3 hooks/clickup_rich_comment.py '<existing_comment_id>' <<'EOF'
## Test Section
- `foo()` — does something
  ref: https://example.com/docs

**IMPORTANTE**
One config record (`customrecord_acme_config`) per account.
EOF
```

Open the task in ClickUp — the comment should show a header, bullet list, inline code, and bold text.

### End-to-end via agent

1. Ask your agent to post a comment on a ClickUp task via MCP.
2. Open the task in ClickUp.
3. Confirm headers, lists, and code blocks render natively.

If formatting is still plain, check the Hooks output channel in Cursor or hook stderr logs.

---

## Optional: agent style guide

The hooks work with any `comment_text` the agent writes. For consistently well-structured technical comments, install the optional style guide:

| Environment | Install |
|-------------|---------|
| Claude Code (plugin) | Included when you [install the plugin](#install-as-a-claude-code-plugin-recommended-for-claude-code-users) |
| Claude Code (manual) | `cp SKILL.md ~/.claude/skills/clickup-comment-style/SKILL.md` |
| Claude.ai | Upload folder as personal skill (Settings → Capabilities → Skills) |
| Cursor (project) | `cp .cursor/rules/clickup-comment-style.mdc your-project/.cursor/rules/` |
| Cursor (user) | `cp .cursor/rules/clickup-comment-style.mdc ~/.cursor/rules/` |

The style guide teaches a plain-text dialect (bullets `•`, dividers, backticks, raw URLs) that reads well without the hook and converts cleanly with it. See [`SKILL.md`](SKILL.md).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `jq not found` in hook logs | Install jq: `brew install jq` (macOS) or `apt install jq` (Linux) |
| `CLICKUP_API_TOKEN is not set` | Run `export CLICKUP_API_TOKEN='pk_...'` or re-run `./install.sh` |
| Token set but hook still skips | IDE hooks may not inherit your shell profile. Add export to `~/.zshrc` and restart the IDE |
| Comment still plain after hook | Check Hooks output channel; verify `comment_id` in hook payload |
| Claude Code hook not firing | Re-run `python3 scripts/merge_claude_hooks.py ~/.claude/settings.json "$(pwd)/hooks/claude-code.sh"` and restart session |
| Cursor adds latency | Hooks run synchronously; large comments may slow the agent turn slightly |

### Discover the MCP tool name (optional)

The default regex matcher `mcp__.*__clickup_create_task_comment` usually works without discovery. If you need an exact matcher:

1. `python3 scripts/merge_claude_hooks.py --suggest-matcher` — hints from local MCP config or debug log.
2. Or temporarily point Cursor `afterMCPExecution` to `scripts/detect-mcp-tool-name.sh`, post a test comment, read `~/.cursor/clickup-mcp-debug.log`.

---

## Repository layout

```
├── .claude-plugin/
│   └── marketplace.json              # Claude Code marketplace catalog
├── plugin/                           # installable Claude Code plugin
│   ├── .claude-plugin/plugin.json
│   ├── hooks/hooks.json
│   ├── scripts/claude-code.sh
│   ├── scripts/clickup_rich_comment.py  → symlink to hooks/
│   └── SKILL.md                      → symlink to repo root
├── install.sh                        # interactive setup (start here)
├── README.md
├── LICENSE
├── .env.example
├── hooks/
│   ├── clickup_rich_comment.py       # text → ops + PUT
│   ├── claude-code.sh
│   └── cursor.sh
├── config-examples/
│   ├── claude-settings.json
│   └── cursor-hooks.json
├── scripts/
│   ├── merge_claude_hooks.py
│   └── detect-mcp-tool-name.sh
├── SKILL.md                          # optional agent style guide
├── .cursor/rules/clickup-comment-style.mdc
└── CONTRIBUTING.md
```

## Limitations

- Preprocessor does not cover every edge case — see [CONTRIBUTING.md](CONTRIBUTING.md).
- Inline `@mentions` are not converted (use MCP `assignee` parameter).
- `PUT` with `comment` ops is documented in [comment formatting](https://developer.clickup.com/docs/comment-formatting) but not fully in the public OpenAPI spec.
- Cursor hooks run synchronously.
- Re-running the hook overwrites the comment with ops derived from `comment_text` (idempotent).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
