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

// Walks a transcript and produces one entry per `#task` opener — status reflects whether a subsequent `#done`/`#skip` closed it; msgs counts every post inside the range.
export function buildTasks(messages) {
  const tasks = [];
  let current = null;
  for (const m of messages || []) {
    const c = classifyMessage(m.body);
    if (c.variant === 'task') {
      if (current) tasks.push(current);
      current = {
        id: c.task?.slug || `t-${m.seq ?? tasks.length + 1}`,
        seq: m.seq,
        slug: c.task?.slug || null,
        title: c.task?.title || '',
        status: 'open',
        msgs: 1,
      };
    } else if (current) {
      current.msgs += 1;
      if (c.variant === 'done') {
        current.status = 'done';
        tasks.push(current);
        current = null;
      } else if (c.variant === 'skip') {
        current.status = 'skip';
        tasks.push(current);
        current = null;
      } else if (current.status === 'open') {
        current.status = 'working';
      }
    }
  }
  if (current) tasks.push(current);
  return tasks;
}

export function classifyMessage(body) {
  const task = parseTaskOpen(body);
  if (task) return { variant: 'task', task };
  const working = parseWorking(body);
  if (working) return { variant: 'working', text: working.content };
  const done = parseDone(body);
  if (done) return { variant: 'done', text: done.content };
  const skip = parseSkip(body);
  if (skip) return { variant: 'skip', text: skip.content };
  return { variant: 'message', text: body };
}
