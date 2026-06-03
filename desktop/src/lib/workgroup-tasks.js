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

// Single resolved classification for a post body. A post with BOTH a #task
// and a #done at line starts is prose (mirrors alpi parse_post ambiguity) —
// this is the one place the desktop renderer must agree with the backend.
export function classifyMessage(body) {
  const task = parseTaskOpen(body);
  const done = parseDone(body);
  if (task && done) return { variant: "message", text: body };
  if (task) return { variant: "task", task };
  const working = parseWorking(body);
  if (working) return { variant: "working", text: working.content };
  if (done) return { variant: "done", text: done.content };
  const skip = parseSkip(body);
  if (skip) return { variant: "skip", text: skip.content };
  return { variant: "message", text: body };
}

// Halted: the latest task closed `#done BLOCKED · …` and nothing re-tasked after.
export function findBlocked(messages, hubPubkey = null) {
  const t = findLatestTask(messages, hubPubkey);
  if (!t || t.state !== "done") return null;
  const reason = t.result || "";
  return /^\s*blocked\b/i.test(reason) ? { slug: t.slug, reason } : null;
}

export function canonicalPhase(slug, pipeline) {
  if (!slug || !pipeline) return null;
  if (pipeline.includes(slug)) return slug;
  for (const p of [...pipeline].sort((a, b) => b.length - a.length)) {
    if (slug.startsWith(`${p}-`)) return p;
  }
  return null;
}

export function pipelineState(pipeline, messages, hubPubkey = null) {
  if (!pipeline || pipeline.length === 0) return [];
  const completed = new Set();
  const seqByPhase = {};
  let openSlug = null;
  let cur = null;
  for (const m of messages || []) {
    const fromHub = !hubPubkey || m.from_pubkey === hubPubkey;
    const cls = classifyMessage(m.body);
    if (cls.variant === "task" && fromHub) {
      cur = { slug: cls.task.slug, result: null };
      openSlug = cls.task.slug;
      const ph = canonicalPhase(cls.task.slug, pipeline);
      if (ph) seqByPhase[ph] = m.seq;
    } else if (cur && fromHub && cls.variant === "done") {
      const ph = canonicalPhase(cur.slug, pipeline);
      if (ph) {
        seqByPhase[ph] = m.seq;
        if (!/^\s*blocked\b/i.test(cls.text || "")) completed.add(ph);
      }
      cur = null;
      openSlug = null;
    }
  }
  const blocked = findBlocked(messages, hubPubkey);
  const blockedPhase = blocked ? canonicalPhase(blocked.slug, pipeline) : null;
  const currentPhase = openSlug ? canonicalPhase(openSlug, pipeline) : null;
  return pipeline.map((slug) => {
    let state = "pending";
    if (slug === blockedPhase) state = "blocked";
    else if (slug === currentPhase) state = "current";
    else if (completed.has(slug)) state = "completed";
    return { slug, state, seq: seqByPhase[slug] ?? null };
  });
}

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
