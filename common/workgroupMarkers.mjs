export const TASK_OPEN_LINE_RE = /^(?:@\S+\s+)*#task\s+#([A-Za-z0-9][A-Za-z0-9_-]{0,63})(?:\s+(.+?))?\s*$/im;
const TASK_INTENT_LINE_RE = /^(?:@\S+\s+)*#task\b.*$/im;
const DONE_LINE_RE = /^(?:@\S+\s+)*#done[ \t]*/im;
const WORKING_LINE_RE = /^(?:@\S+\s+)*#working[ \t]*/im;
const SKIP_LINE_RE = /^(?:@\S+\s+)*#skip[ \t]*/im;
const SKIPPED_CLOSE_RE = /^skipped\s*·\s*\S/i;

export function parseTaskOpen(body) {
  const lines = String(body || "").split("\n");
  for (let i = 0; i < lines.length; i += 1) {
    const m = TASK_OPEN_LINE_RE.exec(lines[i]);
    if (m) {
      const slug = m[1].toLowerCase();
      const title = (m[2] ?? "").trim();
      const rest = lines.slice(i + 1).join("\n").trim();
      const headline = title ? `**#${slug}** ${title}` : `**#${slug}**`;
      return {
        slug,
        title,
        content: rest ? `${headline}\n\n${rest}` : headline,
      };
    }
  }
  return null;
}

export function validateTaskShape(body) {
  const text = String(body || "");
  if (!TASK_INTENT_LINE_RE.test(text)) return { ok: true };
  if (TASK_OPEN_LINE_RE.test(text)) return { ok: true };
  return {
    ok: false,
    error: "`#task` must be followed by `#<slug>` (e.g. `#task #onboarding-friction-top3 …`).",
  };
}

function stripMarker(body, markerRe) {
  const text = String(body || "");
  if (!markerRe.test(text)) return null;
  return text.replace(markerRe, "").trim();
}

export function parseDone(body) {
  const content = stripMarker(body, DONE_LINE_RE);
  return content === null ? null : { content };
}

export function parseWorking(body) {
  const content = stripMarker(body, WORKING_LINE_RE);
  return content === null ? null : { content };
}

export function parseSkip(body) {
  const content = stripMarker(body, SKIP_LINE_RE);
  return content === null ? null : { content };
}

export function classifyMessage(body) {
  const task = parseTaskOpen(body);
  const done = parseDone(body);
  // A post carrying both #task and #done is prose, not a lifecycle event — mirrors alpi parse_post.
  if (task && done) return { variant: "message", text: body };
  if (task) return { variant: "task", task };
  const working = parseWorking(body);
  if (working) return { variant: "working", text: working.content };
  if (done) return { variant: "done", text: done.content };
  const skip = parseSkip(body);
  if (skip) return { variant: "skip", text: skip.content };
  return { variant: "message", text: body };
}

// Vocabulary and precedence mirror the daemon fold `_attempt_state` in alpi/host/workgroup.py.
export function closeStatus(result) {
  const text = String(result ?? "").trim();
  if (/^blocked\b/i.test(text)) return "blocked";
  if (SKIPPED_CLOSE_RE.test(text)) return "skipped";
  if (/^preempted\b/i.test(text)) return "preempted";
  return "done";
}
