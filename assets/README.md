# Demo GIF spec

The main README references `assets/demo.gif` as a before/after demo. Record and commit the GIF here when ready.

## Layout

Split-screen, side by side — real ClickUp UI captures (not mockups):

| Panel | Content |
|-------|---------|
| **Left — Without hook** | ClickUp task comment showing literal markdown: `## Section Title`, `` `inline_code` ``, `- bullet item`, `**bold**` all visible as raw text |
| **Right — With hook** | Same comment content after the hook runs: native header, bullet list, inline code styling, bold text |

## Recording tips

- Use the same ClickUp task and the same agent comment text on both sides.
- Left: post via MCP with the hook disabled (or before install).
- Right: post via MCP with the plugin/hook enabled.
- Target duration: **6 seconds**; loop-friendly.
- Aspect ratio: **9:16** (vertical) or **16:9** (horizontal) — pick whichever fits your capture setup.
- Optional burned-in labels (e.g. "Without hook" / "With hook") to make the contrast obvious at a glance.
- Capture the ClickUp comment card UI, not the IDE — the contrast should be obvious at a glance.

## File

Save as `assets/demo.gif` and remove the `<!-- TODO: record assets/demo.gif -->` comment from the root README once committed.
