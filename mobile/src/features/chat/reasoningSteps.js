function num(v) {
  return typeof v === 'number' && Number.isFinite(v) ? v : NaN;
}

function segmentSeconds(turn, tools, i) {
  const start = num(tools[i].at);
  const prevEnd = i === 0 ? num(turn.at) : num(tools[i - 1].at) + num(tools[i - 1].duration_s);
  if (Number.isFinite(start) && Number.isFinite(prevEnd) && start >= prevEnd) {
    return start - prevEnd;
  }
  return i === 0 ? num(turn.reasoned_s) : NaN;
}

export function reasoningSteps(turn, { active = false } = {}) {
  const tools = Array.isArray(turn?.tools) ? turn.tools : [];
  const steps = [];
  let group = null;
  const flush = () => {
    if (group && group.tools.length) steps.push(group);
    group = null;
  };
  const shown = [];
  for (let i = 0; i < tools.length; i += 1) {
    const t = tools[i];
    const text = String(t.reasoning ?? '').trim();
    if (text) {
      flush();
      const seconds = segmentSeconds(turn, tools, i);
      steps.push({ kind: 'reasoning', text, seconds: Number.isFinite(seconds) ? seconds : undefined });
      shown.push(text);
    }
    if (t.name === 'ask_user') {
      flush();
      steps.push({
        kind: 'askUser',
        question: t.args?.question ?? '',
        result: String(t.output ?? t.result ?? '').trim(),
        tool: t,
      });
      continue;
    }
    if (!group) group = { kind: 'tools', tools: [] };
    group.tools.push(t);
  }
  flush();
  // turn.reasoning is the join of every part incl. per-tool ones — strip shown prefixes or they double-render.
  let trailing = String(turn?.reasoning ?? '').trim();
  for (const text of shown) {
    const rest = trailing.replace(/^\s+/, '');
    if (rest.startsWith(text)) trailing = rest.slice(text.length);
    else break;
  }
  trailing = trailing.trim();
  if (trailing) {
    const seconds = tools.length === 0 ? num(turn?.reasoned_s) : NaN;
    steps.push({
      kind: 'reasoning',
      text: trailing,
      seconds: Number.isFinite(seconds) ? seconds : undefined,
      trailing: true,
    });
  }
  // Empty trailing = the live "thinking" header (State A renders with no text yet).
  if (active && !steps.some((s) => s.trailing) && !tools.some((t) => t.ok == null)) {
    steps.push({ kind: 'reasoning', text: '', trailing: true });
  }
  return steps;
}
