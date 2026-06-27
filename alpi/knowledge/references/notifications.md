# Notifications answer pack

## Answer directly

`notify` pushes a report-grade message to the owner's own Alpi apps (TUI,
desktop, mobile). Write for **quality, not validity** — the daemon
normalizes the content to the allowed subset on the way in, so you never
have to police format. A notification is read once in a narrow column:
make it scannable, not a wall of text. To reach a third party use the
`email` tool, not `notify`.

## When to call

- The user asks to be notified / pinged / alerted / reminded / messaged —
  even mid-chat, that is an order to call `notify`.
- Proactively, for deferred or async news: a reminder coming due, a long
  task finished, "I noticed X".
- Do NOT fire just to duplicate an answer the user is already reading live
  and never asked to be pushed.

## How to write one (allowed elements)

A study can arrive here, so there is a three-level hierarchy:

| Element | Markdown | Use for |
|---|---|---|
| Title | `title` field, or first line | the report title (lead when no `title`) |
| Heading | `## Section` | a major section of a long study |
| Subheading | `**Label:** rest…` / `**Label**` / `### Sub` | scannable subsection head (≤32 chars, ≤5 words) |
| Paragraph | plain text | the body |
| Emphasis | `**bold**`, `*italic*`, `` `code` `` | inline only |
| List | `- item` / `1. item` | bullets / ranked points |
| Quote | `> text` | a quoted line |
| Table | `\| a \| b \|` + `\| --- \|` | small comparison (channel × metric); scrolls if wide |
| Code block | ```` ```…``` ```` | a short trace or config |
| Status | 🔴 🟡 🟢 | severity — the ONLY emoji that survive |

A good daily-summary shape: a lead sentence, then `## Embudo`, with
`**Veredicto:**` / `**Volumen:**` subsections, bullets or a small table
under each, and 🔴🟡🟢 to flag status.

## Auto-simplified (don't bother — it is downgraded for you)

- `####+` deep headings → capped at two levels (heading + subheading)
- images → stripped (alt text kept); describe in prose
- `[text](url)` → just the text (deep-links ride the notification header)
- `---`, raw HTML → removed / stripped
- nested lists → flattened to one level
- every emoji except 🔴🟡🟢 → stripped

## Decision rules

- Set `title` for a short headline shown bold above the body; omit for a
  body-only note. The title is NOT repeated in the body.
- `type`: `info` (neutral) | `warning` (prominent) | `error` (red alert).
- Keep tables small — they scroll horizontally in a narrow column. Deep
  multi-level nesting still belongs in CHAT, not here.

## What not to promise

- No images, no deeply nested structure (the rich surface is chat).
- Styling (width, sizes, spacing) is each app's concern, not the message.

## Related topics

- tools — the full tool surface (notify, email, outputs)
- profiles — where outputs/notifications are stored per profile
