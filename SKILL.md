---
name: clickup-comment-style
description: >-
  Format ClickUp task comments in a consistent technical style (tone, detail, structure).
  Use ALWAYS when creating or editing ClickUp comments via MCP (e.g. clickup_create_task_comment),
  even if the user does not mention style or formatting. KEY (verified live): comment_text only
  renders inline code (backticks) and raw URLs (auto-link). Everything else (## headers, **bold**,
  *italic*, ~~strike~~, [txt](url), - bullets, 1. lists, > quotes, ``` fences) appears LITERAL.
  This skill uses backticks + raw URLs for what renders, and plain-text structure for everything else.
---

# ClickUp Comment Style

Skill for writing technical ClickUp comments with a consistent voice, respecting exactly what
the MCP channel renders.

## What comment_text renders (verified live — read first)

The MCP `clickup_create_task_comment` only writes `comment_text` (string). ClickUp's renderer
applies a minimal inline markdown subset. Confirmed behavior on the task card:

Renders (use):
• Inline code with backticks: `get_customer_orders` → displays as code.
• Raw URL: https://... → auto-linked.

Does NOT render — appears LITERAL (do not use for formatting):
• Emphasis: `**bold**`, `*italic*`, `~~strikethrough~~`
• Markdown links: `[text](url)` (use raw URL instead)
• Block: `##`/`###` headers, `-`/`*` bullets, `1.` lists, `>` blockquote, ``` fences

Operational rule: backticks for identifiers, raw URLs for links, and all structure/emphasis
via plain-text. Native formatting (headers/bold/code-block) lives in the `comment` field
(array of ops), which the MCP does not expose.

## With the rich-text hook installed

If you have configured the optional post-MCP hook (`clickup_rich_comment.py`), keep writing
the **same plain-text dialect** described below. Do not switch to `##` or `**bold**` for the
agent — the hook preprocesses this dialect and upgrades the comment to native rich text via
`PUT /api/v2/comment/{comment_id}`. Without the hook, plain-text alone must still read well.

---

## Content (tone, language, detail)

Voice and tone:
- First person, active voice: "I created…", "I added…", "I propose…". Spanish: "creé", "decidí probar".
- Direct and factual. No greetings, filler, or closings. Start on substance in the first line.
- Peer-to-peer technical: assume domain knowledge. Explain non-obvious decisions, not basics.
- Honest about limits: document what is NOT covered, assumptions, and risks.

Language (mirror context):
- English by default for client/international audience; Spanish for internal discussion.
- Match the language of the thread/task.

Detail level:
- High: what + how + why. Concrete examples (request/response, IDs, URLs).
- For code: name the function/script/record affected (in backticks) and link the commit.
- For decisions/research: conclusion first, then detail.

Governing principle: technical claim → evidence (`ref:` doc, `commit ref:` commit, or raw URL).
Do not invent data: if a commit/URL/ID is missing, ask or leave an explicit placeholder.

---

## Format

What renders (use):
- Identifiers ALWAYS in backticks: functions `getOptions(productId)`, files `client.py`,
  fields `custbody_acme_synced`, records `customrecord_acme_config`, endpoints
  `POST /v3/storefront/...`, enums `PACKAGE_DELIVERED`.
- Links: raw URL always (auto-links). Never `[text](url)` (renders literal).

Structure and emphasis (plain-text, because the rest does not render):
- Section titles: own line, Title Case. Major sections between 40-character box dividers:
  `────────────────────────────────────────`. Numbered: `1. Title`.
- Strong emphasis / warnings: UPPERCASE (`IMPORTANTE`, `OBSOLETO`, `MUST`). Do NOT use
  `**bold**` — it renders literal.
- Labels/subtitles: own line ending with `:` (`Notas:`, `Approach:`, `Results:`, `Endpoint:`).
- Bullets: `• ` (indent 2). Sub-bullets: `– ` (en dash, indent 4–6).
- Steps: `1.` `2.` `3.` at line start.
- Multi-line code snippets: indent each line with 4 spaces. NO fences.
- Flows: arrows `→`.
- Refs: own line with `ref:` / `commit ref:` / `Doc:` + raw URL.
- Direct someone: use the tool's `assignee` parameter, NOT `@inline` (does not resolve via
  API; real tags require the `comment` array, not exposed by MCP).

---

## Templates by comment type

A. Work report → title per component, prose, `• function()` in backticks + what it does,
   `commit ref:`/`ref:` on own line.

B. Feature/behavior doc → sections with divider/numbering, bullets `•` with identifiers in
   backticks, limits section (`Notas:` / `IMPORTANTE`).

C. API/endpoint spec → labels `Endpoint:` / `Method:` (`POST` in backticks) / `Body:` /
   `Response:`, snippets indented 4 spaces, example with realistic data.

D. Multi-part plan → intro, list `1. 2. 3.`, owner at end of each step (`-- ALICE` / `-- BOB`).

E. Decision / research (PoC) → conclusion first, divider, numbered approaches with
   `Approach:` / `Results:`, methods in backticks, citations with `Doc:`.

F. Quoted content → clear prefix + indent 4 spaces (not `>`).

---

## Few-shots (backticks + raw URLs + plain-text structure)

### A — Work report
```
Catalog Service
I added three endpoint calls to the acme-connector catalog REST API.

• `getOptions(productId)` — pulls all product options based on the product ID.
  ref: https://developer.example.com/docs/rest-catalog/product-variant-options/values
• `createVariant(productId, variantData)` — creates a variant and assigns it to a product.
  ref: https://developer.example.com/docs/rest-catalog/product-variants

commit ref: https://github.com/acme-org/acme-connector/commit/abc123def456
```

### B — Feature / behavior documentation
```
────────────────────────────────────────
1. Order creation, update and cancel
────────────────────────────────────────
• Added UserEvent script that runs when a Sales Order is created or edited in the ERP.
• Orders created in the platform have the body field `custbody_acme_synced` marked.

Notas:
• Item maintenance is the client's responsibility (the API offers no method to add items).

IMPORTANTE
We cannot have more than one config record (`customrecord_acme_config`) per account.
```

### C — API / endpoint spec
```
I created an endpoint for test order creation via a hosted scriptlet.

Endpoint: https://api.example.com/v1/orders/create
Method:   `POST`

Body:
    {
      lineItems: [
        { sku: string, quantity: number, isPrime: boolean }
      ]
    }

Response example:
    { "status": 201, "id": "ORG-123", "orderUrl": "https://app.example.com/orders/ORG-123" }
```

### D — Multi-part plan
```
Moving to the production account plan
I propose the following approach, disturbing their operation as little as possible.

1. Deploy the integration and leave all scripts deactivated.            -- ALICE
2. Migrate items from the ERP to the external platform.                 -- BOB
3. Test orders MUST have at least one already-migrated item.            -- ALICE OR BOB
```

### E — Decision / research (PoC)
```
Final Conclusion: Based on Proof of Concepts
The best way to handle real-time events without freezing the ERP UI is a middleware
acting as a bridge between the edited-record context and the REST endpoint.

Record update → middleware → response to ERP → async to REST handler → notification service

────────────────────────────────────────
1. Execute REST handler on UserEvent afterSubmit asynchronously
────────────────────────────────────────
Approach: call the handler from afterSubmit via `https.request(...)` and `.promise(...)`.
Results: the UI froze 'loading' for the full 60s wait, then finished. Async did not help.
Doc: do not run a UE script from another UE; extract the shared code into a module.
```

### F — Quoted content
```
Feedback from client:
    Please change the shipping method code. Instead of "dhl_acme_standard"
    use: dhl_acme_business.
```

---

## Checklist before posting

1. Only backticks and raw URLs as markdown? (NO `##`, `**`, `*`, `~~`, `[]()`, `-`, `>`, fences)
2. Identifiers in backticks?
3. First person, direct, no filler?
4. Correct language for the thread audience?
5. Each technical claim with `ref:` / `commit ref:` / raw URL?
6. Plain-text structure: divider/numbering, bullets `•`, snippets indented 4 spaces, flows `→`?
7. Emphasis via UPPERCASE and warnings with `IMPORTANTE` (not `**bold**`)?
8. If directed at someone, used `assignee` parameter (not `@inline`)?
