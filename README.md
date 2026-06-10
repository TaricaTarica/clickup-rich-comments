# clickup-rich-comments

**Your ClickUp MCP posts `## broken` comments. This fixes them.**
Auto-upgrades every agent comment to native rich text — headers, bold, lists, code.
Works with Claude Code and Cursor.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3](https://img.shields.io/badge/python-3-3776ab.svg)](hooks/clickup_rich_comment.py)
[![GitHub stars](https://img.shields.io/github/stars/TaricaTarica/clickup-rich-comments?style=social)](https://github.com/TaricaTarica/clickup-rich-comments)

<!-- Once there's traction, add a "Used by / Featured in" or a short testimonial here. -->

This repo ships a post-hook plus an optional skill/plugin named `clickup-comment-style` (the install id in `/plugin install ...`).

<!-- TODO: record assets/demo.gif — 6s split-screen: LEFT = comment with literal ## / **bold** /
backticks, RIGHT = same comment rendered as native headers/bold/lists. See assets/README.md -->
![Before and after: ClickUp comment with literal ## and backticks on the left, rendered native rich text on the right](assets/demo.gif)

## The problem

Your agent writes a nicely formatted comment:

```
## Deploy steps
1. Run `migrate`
2. Restart the worker
```

ClickUp shows your team this — raw, unrendered:

```
## Deploy steps
1. Run `migrate`
2. Restart the worker
```

Same text. The `##` and `1.` never render: the MCP only writes plain `comment_text`, and ClickUp doesn't parse Markdown there.

## What renders / what doesn't

| In `comment_text` | Renders in ClickUp UI? |
|-------------------|------------------------|
| Inline code `` `identifier` `` | Yes |
| Raw URL `https://...` | Yes (auto-link) |
| `**bold**`, `*italic*`, `~~strike~~` | No — literal |
| `[text](url)` | No — literal |
| `##` headers, `-` bullets, `1.` lists | No — literal |
| `>` blockquote, ` ``` ` fences | No — literal |

## Quickstart

```bash
git clone https://github.com/TaricaTarica/clickup-rich-comments.git
cd clickup-rich-comments
./install.sh
```

The installer checks prerequisites, guides you through `CLICKUP_API_TOKEN` setup, and configures hooks for Cursor and Claude Code automatically. Takes about two minutes.

**Requirements:** `python3`, `jq` (for hook wrappers). No pip packages.

## Install

> ⚠️ **Pick one install method.** If you install a plugin, don't also run `./install.sh`
> (or merge hooks manually) — you'd run the upgrade twice per comment.

<details>
<summary><b>Install as a Cursor plugin</b> — recommended for Cursor users</summary>

<span id="install-as-a-cursor-plugin-recommended-for-cursor-users"></span>

Install the hook and style guide in one step via the Cursor plugin marketplace:

```
/plugin marketplace add TaricaTarica/clickup-rich-comments
```

Then in a Cursor session:

```
/plugin install clickup-comment-style@clickup-rich-comments
```

Or use `/add-plugin` and search for `clickup-comment-style`.

After install, restart Cursor or run **Developer: Reload Window**. Hook changes are not hot-reloaded; `SKILL.md` and rule updates may require a reload.

**Requirements:** `python3`, `jq`, and `CLICKUP_API_TOKEN` in your environment (see [token setup](#step-by-step-get-your-clickup_api_token)). The plugin installs the mechanism only — it never embeds or ships credentials.

**What you get:** an `afterMCPExecution` hook that upgrades `clickup_create_task_comment` output to native rich text, plus the comment style guide skill and rule.

**ClickUp MCP:** must already be configured separately. This plugin does not declare `mcp.json` — adding ClickUp MCP again would conflict with your existing setup.

**Marketplace source:** add the marketplace via Git shorthand (`owner/repo`) or a git URL. Do not add it via a direct URL to `marketplace.json` — relative plugin paths (`./plugin-cursor`) only resolve when the marketplace is fetched from a git repository.

**Test locally before publishing:**

```bash
ln -sf "$(pwd)/plugin-cursor" ~/.cursor/plugins/local/clickup-comment-style
# Developer: Reload Window → verify rules, skills, and hooks in Settings
```

If symlinks are missing after clone (common on Windows), run `./scripts/sync-plugins.sh`.

</details>

<details>
<summary><b>Install as a Claude Code plugin</b> — recommended for Claude Code users</summary>

<span id="install-as-a-claude-code-plugin-recommended-for-claude-code-users"></span>

For Claude Code, install the hook and style guide in one step via the plugin marketplace:

```bash
claude plugin marketplace add TaricaTarica/clickup-rich-comments
```

Then in a Claude Code session:

```
/plugin install clickup-comment-style@clickup-rich-comments
```

After install, restart the session or run `/reload-plugins`. Hook changes are not hot-reloaded; `SKILL.md` updates are.

**Requirements:** `python3`, `jq`, and `CLICKUP_API_TOKEN` in your environment (see [token setup](#step-by-step-get-your-clickup_api_token)). The plugin installs the mechanism only — it never embeds or ships credentials.

**What you get:** a `PostToolUse` hook that upgrades `clickup_create_task_comment` output to native rich text, plus the comment style guide skill.

**ClickUp MCP:** must already be configured separately (OAuth). This plugin does not declare `.mcp.json` — adding ClickUp MCP again would conflict with your existing setup.

**Marketplace source:** add the marketplace via Git shorthand (`owner/repo`) or a git URL. Do not add it via a direct URL to `marketplace.json` — relative plugin paths (`./plugin`) only resolve when the marketplace is fetched from a git repository.

</details>

<details>
<summary><b>Manual / install.sh</b> — universal fallback</summary>

`./install.sh` is the universal fallback when you prefer not to use a marketplace plugin, or when you want hooks in both Cursor and Claude Code from one script.

### Cursor (manual)

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

Restart Cursor or save `hooks.json` to reload hooks.

### Claude Code (manual)

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

</details>

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

## Why this exists

The MCP only writes `comment_text` — a plain string with minimal inline rendering. Native formatting (headers, lists, code blocks) lives in the separate `comment` field as a Quill-delta ops array, which the MCP does not expose. This hook reads `comment_text` after the MCP call and rewrites the comment via the documented `PUT` endpoint. See [ClickUp comment formatting](https://developer.clickup.com/docs/comment-formatting).

---

## Reference

## Claude Code vs Cursor

| | Claude Code plugin | Cursor plugin |
|---|-------------------|---------------|
| Hook event | `PostToolUse` | `afterMCPExecution` |
| Config file | `plugin/hooks/hooks.json` or `~/.claude/settings.json` | `plugin-cursor/hooks/hooks.json` or `~/.cursor/hooks.json` |
| Matcher | Regex in config: `mcp__.*__clickup_create_task_comment` | None — `cursor.sh` filters `tool_name` internally |
| `tool_name` | `mcp__<server>__clickup_create_task_comment` | `clickup_create_task_comment` (no MCP prefix) |
| `tool_input` | JSON object | JSON string — unwrap with `jq 'fromjson'` |
| Comment ID | `tool_response.comment_id` | `tool_output.comment_id` |
| Async | Supported (`"async": true`) | Not documented (runs synchronously) |

## Security

Hooks run **without a sandbox** — they execute with your user permissions, the same as any local shell script Cursor or Claude Code invokes.

What the hook does:

1. Reads the MCP tool payload from stdin (tool name, comment text, comment ID).
2. If the tool is `clickup_create_task_comment` and the call succeeded, calls `clickup_rich_comment.py`.
3. The Python script sends one `PUT` request to `https://api.clickup.com/api/v2/comment/{id}` using `CLICKUP_API_TOKEN` from your environment.
4. On any error (missing token, missing `jq`, API failure), the hook logs to stderr and **exits 0** — your agent session is never blocked.

The repo contains no credentials. Review [`hooks/cursor.sh`](hooks/cursor.sh), [`hooks/claude-code.sh`](hooks/claude-code.sh), and [`hooks/clickup_rich_comment.py`](hooks/clickup_rich_comment.py) before installing.

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

<details>
<summary><b>Optional: agent style guide</b> — teaches agents a comment dialect that converts cleanly with the hook</summary>

The hooks work with any `comment_text` the agent writes. For consistently well-structured technical comments, install the optional style guide:

| Environment | Install |
|-------------|---------|
| Cursor (plugin) | Included when you [install the Cursor plugin](#install-as-a-cursor-plugin-recommended-for-cursor-users) |
| Claude Code (plugin) | Included when you [install the Claude Code plugin](#install-as-a-claude-code-plugin-recommended-for-claude-code-users) |
| Claude Code (manual) | `cp SKILL.md ~/.claude/skills/clickup-comment-style/SKILL.md` |
| Claude.ai | Upload folder as personal skill (Settings → Capabilities → Skills) |
| Cursor (project) | `cp .cursor/rules/clickup-comment-style.mdc your-project/.cursor/rules/` |
| Cursor (user) | `cp .cursor/rules/clickup-comment-style.mdc ~/.cursor/rules/` |

The style guide teaches a plain-text dialect (bullets `•`, dividers, backticks, raw URLs) that reads well without the hook and converts cleanly with it. See [`SKILL.md`](SKILL.md).

</details>

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `jq not found` in hook logs | Install jq: `brew install jq` (macOS) or `apt install jq` (Linux) |
| `CLICKUP_API_TOKEN is not set` | Run `export CLICKUP_API_TOKEN='pk_...'` or re-run `./install.sh` |
| Token set but hook still skips | IDE hooks may not inherit your shell profile. Add export to `~/.zshrc` and restart the IDE |
| Comment still plain after hook | Check Hooks output channel; verify `comment_id` in hook payload |
| Claude Code hook not firing | Re-run `python3 scripts/merge_claude_hooks.py ~/.claude/settings.json "$(pwd)/hooks/claude-code.sh"` and restart session |
| Cursor adds latency | Hooks run synchronously; large comments may slow the agent turn slightly |
| Plugin symlinks missing | Run `./scripts/sync-plugins.sh` after clone |

## Discover the MCP tool name (optional)

The default regex matcher `mcp__.*__clickup_create_task_comment` usually works without discovery. If you need an exact matcher:

1. `python3 scripts/merge_claude_hooks.py --suggest-matcher` — hints from local MCP config or debug log.
2. Or temporarily point Cursor `afterMCPExecution` to `scripts/detect-mcp-tool-name.sh`, post a test comment, read `~/.cursor/clickup-mcp-debug.log`.

## Repository layout

```
├── .claude-plugin/
│   └── marketplace.json              # Claude Code marketplace catalog
├── .cursor-plugin/
│   └── marketplace.json              # Cursor marketplace catalog
├── plugin/                           # installable Claude Code plugin
│   ├── .claude-plugin/plugin.json
│   ├── hooks/hooks.json
│   ├── scripts/claude-code.sh
│   ├── scripts/clickup_rich_comment.py  → symlink to hooks/
│   └── SKILL.md                      → symlink to repo root
├── plugin-cursor/                    # installable Cursor plugin
│   ├── .cursor-plugin/plugin.json
│   ├── hooks/hooks.json
│   ├── scripts/cursor.sh             → symlink to hooks/
│   ├── scripts/clickup_rich_comment.py  → symlink to hooks/
│   ├── skills/clickup-comment-style/SKILL.md  → symlink to repo root
│   └── rules/clickup-comment-style.mdc  → symlink to ../../.cursor/rules/
├── install.sh                        # interactive setup (universal fallback)
├── README.md
├── LICENSE
├── .env.example
├── assets/
│   └── README.md                     # demo GIF recording spec
├── hooks/
│   ├── clickup_rich_comment.py       # text → ops + PUT (source of truth)
│   ├── claude-code.sh
│   └── cursor.sh
├── config-examples/
│   ├── claude-settings.json
│   └── cursor-hooks.json
├── scripts/
│   ├── merge_claude_hooks.py
│   ├── detect-mcp-tool-name.sh
│   └── sync-plugins.sh               # provision plugin symlinks
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
