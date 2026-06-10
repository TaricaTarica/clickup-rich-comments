# Demo GIF spec

The main README references `assets/demo.gif` as a before/after demo. Record and commit the GIF here when ready.

## Layout

Split-screen, side by side:

| Panel | Content |
|-------|---------|
| **Left — Without hook** | ClickUp task comment showing literal markdown: `## Section Title`, `` `inline_code` ``, `- bullet item`, `**bold**` all visible as raw text |
| **Right — With hook** | Same comment content after the hook runs: native header, bullet list, inline code styling, bold text |

## Recording tips

- Use the same ClickUp task and the same agent comment text on both sides.
- Left: post via MCP with the hook disabled (or before install).
- Right: post via MCP with the plugin/hook enabled.
- Keep duration under 10 seconds; loop-friendly.
- Recommended size: 1200×600 px (2:1) or 1280×720.
- Capture the ClickUp comment card UI, not the IDE — the contrast should be obvious at a glance.

## File

Save as `assets/demo.gif` and remove the `<!-- TODO: record demo GIF -->` comment from the root README once committed.
