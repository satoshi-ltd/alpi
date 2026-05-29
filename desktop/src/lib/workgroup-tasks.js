const TASK_RE = /^(?:@\S+\s+)*#task\s+#([A-Za-z0-9][A-Za-z0-9_-]{0,63})(?:\s+(.+?))?\s*$/m;
const DONE_RE = /^(?:@\S+\s+)*#done\s*(.*)$/m;

const TASK_OPEN_LINE_RE = /^(?:@\S+\s+)*#task\s+#([A-Za-z0-9][A-Za-z0-9_-]{0,63})(?:\s+(.+?))?\s*$/im;
const TASK_INTENT_LINE_RE = /^(?:@\S+\s+)*#task\b.*$/im;
const DONE_LINE_RE = /^(?:@\S+\s+)*#done[ \t]*/im;
const WORKING_LINE_RE = /^(?:@\S+\s+)*#working[ \t]*/im;
const SKIP_LINE_RE = /^(?:@\S+\s+)*#skip[ \t]*/im;

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
  // Remove the marker keyword (and any leading @mentions) from its line; keep the rest of the body intact so authors who close with a synthesis above the `#done` line keep that content visible.
  return text.replace(markerRe, "").trim();
}

export const parseDone = (body) => {
  const content = stripMarker(body, DONE_LINE_RE);
  return content === null ? null : { content };
};

export const parseWorking = (body) => {
  const content = stripMarker(body, WORKING_LINE_RE);
  return content === null ? null : { content };
};

export const parseSkip = (body) => {
  const content = stripMarker(body, SKIP_LINE_RE);
  return content === null ? null : { content };
};

export function findLatestTask(messages, hubPubkey = null) {
  if (!messages || messages.length === 0) return null;
  let latest = null;
  for (const m of messages) {
    if (hubPubkey && m.from_pubkey !== hubPubkey) continue;
    const body = m.body || "";
    const taskMatch = TASK_RE.exec(body);
    const doneMatch = DONE_RE.exec(body);
    if (taskMatch && doneMatch) continue; // both markers in one post → prose (mirrors alpi parse_post ambiguity rule)
    if (doneMatch && latest) {
      latest = { ...latest, state: "done", result: doneMatch[1].trim() };
      continue;
    }
    if (taskMatch) {
      const slug = taskMatch[1].toLowerCase();
      const title = (taskMatch[2] ?? "").trim();
      latest = {
        state: "open",
        slug,
        text: title || slug,
        seq: m.seq,
        result: null,
      };
    }
  }
  return latest;
}
