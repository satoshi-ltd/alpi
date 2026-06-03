// 1:1 port of WorkgroupView.jsx marker parsers — anchored to body lines, mentions allowed as prefix.

const TASK_OPEN_LINE_RE = /^(?:@\S+\s+)*#task\s+#([A-Za-z0-9][A-Za-z0-9_-]{0,63})(?:\s+(.+?))?\s*$/im;
const TASK_INTENT_LINE_RE = /^(?:@\S+\s+)*#task\b.*$/im;
const DONE_LINE_RE = /^(?:@\S+\s+)*#done[ \t]*/im;
const WORKING_LINE_RE = /^(?:@\S+\s+)*#working[ \t]*/im;
const SKIP_LINE_RE = /^(?:@\S+\s+)*#skip[ \t]*/im;

export function parseTaskOpen(body) {
  const lines = String(body || '').split('\n');
  for (let i = 0; i < lines.length; i += 1) {
    const m = TASK_OPEN_LINE_RE.exec(lines[i]);
    if (m) {
      const slug = m[1].toLowerCase();
      const title = (m[2] ?? '').trim();
      const rest = lines.slice(i + 1).join('\n').trim();
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
  const text = String(body || '');
  if (!TASK_INTENT_LINE_RE.test(text)) return { ok: true };
  if (TASK_OPEN_LINE_RE.test(text)) return { ok: true };
  return {
    ok: false,
    error: '`#task` must be followed by `#<slug>` (e.g. `#task #onboarding-friction-top3 …`).',
  };
}

function stripMarker(body, markerRe) {
  const text = String(body || '');
  if (!markerRe.test(text)) return null;
  // Strip the marker keyword on its line; preserve any content before or after.
  return text.replace(markerRe, '').trim();
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

// Walks a transcript, one entry per hub `#task` opener. Only the hub opens (`#task`) and closes (`#done`); a member's `#skip`/`#working` are round signals that never touch lifecycle. "skip" status means preempted: the hub opened a new `#task` before closing this one with `#done` (alpi/alp/tasks.py fold_tasks). msgs counts every post inside the range.
export function buildTasks(messages, hubPubkey = null) {
  const tasks = [];
  let current = null;
  for (const m of messages || []) {
    const c = classifyMessage(m.body);
    const fromHub = !hubPubkey || m.from_pubkey === hubPubkey;
    if (c.variant === 'task' && fromHub) {
      if (current) {
        current.status = 'skip';
        tasks.push(current);
      }
      current = {
        id: c.task?.slug || `t-${m.seq ?? tasks.length + 1}`,
        seq: m.seq,
        slug: c.task?.slug || null,
        title: c.task?.title || '',
        status: 'working',
        msgs: 1,
      };
    } else if (current) {
      current.msgs += 1;
      if (c.variant === 'done' && fromHub) {
        current.status = 'done';
        current.result = c.text || '';
        tasks.push(current);
        current = null;
      }
    }
  }
  if (current) tasks.push(current);
  return tasks;
}

// Halted: the latest task closed `#done BLOCKED · …` and nothing re-tasked after.
export function findBlocked(messages, hubPubkey = null) {
  const tasks = buildTasks(messages, hubPubkey);
  const last = tasks[tasks.length - 1];
  if (!last || last.status !== 'done') return null;
  return /^\s*blocked\b/i.test(last.result || '')
    ? { slug: last.slug, reason: last.result }
    : null;
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
    if (cls.variant === 'task' && fromHub) {
      cur = cls.task.slug;
      openSlug = cls.task.slug;
      const ph = canonicalPhase(cls.task.slug, pipeline);
      if (ph) seqByPhase[ph] = m.seq;
    } else if (cur && fromHub && cls.variant === 'done') {
      const ph = canonicalPhase(cur, pipeline);
      if (ph) {
        seqByPhase[ph] = m.seq;
        if (!/^\s*blocked\b/i.test(cls.text || '')) completed.add(ph);
      }
      cur = null;
      openSlug = null;
    }
  }
  const blocked = findBlocked(messages, hubPubkey);
  const blockedPhase = blocked ? canonicalPhase(blocked.slug, pipeline) : null;
  const currentPhase = openSlug ? canonicalPhase(openSlug, pipeline) : null;
  return pipeline.map((slug) => {
    let state = 'pending';
    if (slug === blockedPhase) state = 'blocked';
    else if (slug === currentPhase) state = 'current';
    else if (completed.has(slug)) state = 'completed';
    return { slug, state, seq: seqByPhase[slug] ?? null };
  });
}

export function classifyMessage(body) {
  const task = parseTaskOpen(body);
  const done = parseDone(body);
  // Both #task and #done in one post → prose, no lifecycle event (mirrors alpi parse_post ambiguity rule).
  if (task && done) return { variant: 'message', text: body };
  if (task) return { variant: 'task', task };
  const working = parseWorking(body);
  if (working) return { variant: 'working', text: working.content };
  if (done) return { variant: 'done', text: done.content };
  const skip = parseSkip(body);
  if (skip) return { variant: 'skip', text: skip.content };
  return { variant: 'message', text: body };
}
