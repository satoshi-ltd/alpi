const TASK_RE = /^(?:@\S+\s+)*#task\s+(.+?)\s*$/m;
const DONE_RE = /^(?:@\S+\s+)*#done\s*(.*)$/m;

const TASK_LINE_RE = /^(?:@\S+\s+)*#task\s+(.+?)\s*$/im;
const DONE_LINE_RE = /^(?:@\S+\s+)*#done[ \t]*/im;
const WORKING_LINE_RE = /^(?:@\S+\s+)*#working[ \t]*/im;
const SKIP_LINE_RE = /^(?:@\S+\s+)*#skip[ \t]*/im;
const TASK_SLUG_RE = /^#([A-Za-z0-9][A-Za-z0-9_-]*)(?:\s+(.+))?$/;

export function parseTaskOpen(body) {
  const lines = String(body || "").split("\n");
  for (let i = 0; i < lines.length; i += 1) {
    const m = TASK_LINE_RE.exec(lines[i]);
    if (m) {
      const firstLine = m[1].trim();
      const slugMatch = TASK_SLUG_RE.exec(firstLine);
      const slug = slugMatch ? slugMatch[1].toLowerCase() : null;
      const title = slugMatch ? (slugMatch[2] ?? "").trim() : firstLine;
      const rest = lines.slice(i + 1).join("\n").trim();
      const headline = slug
        ? (title ? `**#${slug}** ${title}` : `**#${slug}**`)
        : title;
      return {
        slug,
        title,
        content: rest ? `${headline}\n\n${rest}` : headline,
      };
    }
  }
  return null;
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
    const doneMatch = DONE_RE.exec(m.body || "");
    if (doneMatch && latest) {
      latest = { ...latest, state: "done", result: doneMatch[1].trim() };
      continue;
    }
    const taskMatch = TASK_RE.exec(m.body || "");
    if (taskMatch) {
      latest = { state: "open", text: taskMatch[1], seq: m.seq, result: null };
    }
  }
  return latest;
}
