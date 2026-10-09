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

A digest of items (mail, PRs, alerts) lists one entry per line as
`- **Name** meta — text`: the sender or subject owner in bold, a short meta
(an address, a repo, a time) after it, then the line itself; the apps draw
each entry as name, meta in small mono and the text below, so keep the meta
short and put the substance in the text.

A memory file past 90 % of its limit and a skill that fails lint or lacks what it requires are filed by the daemon as one `warning` row each, the first time they are flagged; do not notify about them yourself.

A failed scheduled run is filed by the daemon, not by you: its title is
"<job> failed" and its body opens with `**Reason:**`, then `**Exit:**` and
`**Timeout:**` when they apply, with any trace in a ```` ```text ```` block.
The apps draw any `error` row as a card: the labelled lines it opens with as
facts, the rest in order, and the code blocks it ends with folded under Details,
with Run again and Open job when the daemon filed it; a brace-delimited run of
lines in any body (a pasted JSON payload) renders as a code block. Both apps pin
unread `error` and `warning` rows in a Needs you group, so set `type` only when
the owner has to act. Reply starts a new chat with you about the notification: the
desktop attaches it as a Markdown file, the phone quotes its title and body (`> `
lines, clipped) at the top of the message. A digest is
drawn as entries only when it has two or more items, every one a plain `-` bullet
in that form with a plain meta of at most four words; any other list stays a list.

## Which daemons reach the owner

The desktop and phone apps raise notifications from every paired daemon, not
only the connection that is open; the open one arrives at once, the others
within about half a minute while the app runs. A warning row the daemon files
itself (memory or skill attention) shows in the inbox but raises no banner.
On the desktop, coming back to the app within about 20 seconds of a banner opens
what it announced (the chat, the notification, the approval or question, or a
failed job's schedule); on the phone, tapping a banner does. A failed job opens
its failure notification, or the job's page on an older daemon.

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
