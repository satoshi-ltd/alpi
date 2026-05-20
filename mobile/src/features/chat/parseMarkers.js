// 1:1 port of WorkgroupView.jsx marker parsers — anchored to body lines, mentions allowed as prefix.

function findMarkerLine(body, re) {
  for (const line of String(body || '').split('\n')) {
    const m = re.exec(line);
    if (m) return m;
  }
  return null;
}

export function parseTaskOpen(body) {
  const m = findMarkerLine(body, /^(?:@\S+\s+)*#task(?:\s+([A-Za-z0-9_-]+))?(?:\s+(.+?))?\s*$/i);
  if (!m) return null;
  return { taskId: m[1] ?? null, title: (m[2] ?? '').trim() };
}

export function parseWorking(body) {
  const m = findMarkerLine(body, /^(?:@\S+\s+)*#working(?:\s+([^\n]+))?\s*$/i);
  return m ? { reason: (m[1] ?? '').trim() } : null;
}

export function parseSkip(body) {
  const m = findMarkerLine(body, /^(?:@\S+\s+)*#skip(?:\s+([^\n]+))?\s*$/i);
  return m ? { reason: (m[1] ?? '').trim() } : null;
}

export function parseDone(body) {
  const m = findMarkerLine(body, /^(?:@\S+\s+)*#done\s+(.+?)\s*$/i);
  return m ? { result: m[1].trim() } : null;
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
        id: c.task?.taskId || `t-${m.seq ?? tasks.length + 1}`,
        seq: m.seq,
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
  if (working) return { variant: 'working', text: working.reason };
  const done = parseDone(body);
  if (done) return { variant: 'done', text: done.result };
  const skip = parseSkip(body);
  if (skip) return { variant: 'skip', text: skip.reason };
  return { variant: 'message', text: body };
}
