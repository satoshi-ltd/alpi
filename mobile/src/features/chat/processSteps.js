const START_SLACK_S = 1;

export function orderedTools(tools) {
  const list = (Array.isArray(tools) ? tools : []).filter((t) => t?.name !== 'ask_user');
  return list
    .map((t, i) => ({ t, i, at: Number(t.at) }))
    .sort((a, b) => (Number.isFinite(a.at) && Number.isFinite(b.at) ? a.at - b.at : 0) || a.i - b.i)
    .map(({ t }) => t);
}

function trailingAfter(segments, turnReasoning) {
  let rest = String(turnReasoning ?? '').trim();
  for (const seg of segments) {
    const trimmed = rest.replace(/^\s+/, '');
    if (!trimmed.startsWith(seg)) break;
    rest = trimmed.slice(seg.length);
  }
  return rest.trim();
}

export function reasoningFirst(turn, tools) {
  const list = orderedTools(tools);
  if (!list.length) return true;
  if (String(list[0].reasoning ?? '').trim()) return true;
  // stored reasoned_s spans turn start to the first tool; a live stream sums reasoning spans instead
  if (turn?.req) return false;
  const started = Number(turn?.at);
  const reasoned = Number(turn?.reasoned_s);
  const firstTool = Number(list[0].at);
  if (![started, reasoned, firstTool].every(Number.isFinite) || reasoned < 1) return false;
  return started + reasoned <= firstTool + START_SLACK_S;
}

const toolKey = (tool, i) => `t:${tool?.tool_id ?? `${tool?.name}:${i}`}`;

function spanSlots(turn, toolCount) {
  const spans = Array.isArray(turn?.reasoning_spans) ? turn.reasoning_spans : [];
  const at = new Map();
  for (const span of spans) {
    const idx = Number(span?.before_tool);
    if (!Number.isInteger(idx) || idx < 0) continue;
    const pos = Math.min(idx, toolCount);
    const secs = Number(span?.seconds);
    const slot = at.get(pos) ?? { seconds: 0, texts: [] };
    slot.seconds += Number.isFinite(secs) && secs > 0 ? secs : 0;
    const text = String(span?.text ?? '').trim();
    if (text) slot.texts.push(text);
    at.set(pos, slot);
  }
  return at;
}

function withoutShown(text, shown) {
  let rest = String(text ?? '');
  for (const seg of shown) {
    const idx = rest.indexOf(seg);
    if (idx >= 0) rest = rest.slice(0, idx) + rest.slice(idx + seg.length);
  }
  return rest.replace(/\n{3,}/g, '\n\n').trim();
}

function slotText(slot, prose, spanText) {
  if (!spanText) return prose;
  const own = (slot?.texts ?? []).join('\n\n');
  if (!prose || own.includes(prose)) return own;
  return own ? `${own}\n\n${prose}` : prose;
}

function spanSteps(turn, tools, slots, streaming) {
  const raw = Array.isArray(turn?.tools) ? turn.tools : [];
  const shown = [];
  let next = 0;
  raw.forEach((t, i) => {
    if (t?.name !== 'ask_user') shown[i] = tools[next++];
  });
  const perTool = raw.map((t) => String(t?.reasoning ?? '').trim());
  const spanText = [...slots.values()].some((slot) => slot.texts.length);
  const rendered = [];
  const steps = [];
  let run = null;
  const flush = () => {
    if (run) steps.push(run);
    run = null;
  };
  for (let i = 0; i <= raw.length; i += 1) {
    const end = i === raw.length;
    const slot = slots.get(i);
    const prose = end ? '' : perTool[i];
    const live = end && streaming;
    const text = !(slot || prose || live) ? ''
      : end && !spanText ? withoutShown(turn?.reasoning, rendered)
        : slotText(slot, prose, spanText);
    if (live || text || slot?.seconds >= 1) {
      if (text) rendered.push(text);
      flush();
      steps.push({
        kind: 'reasoning',
        key: `r${steps.filter((st) => st.kind === 'reasoning').length}`,
        text,
        seconds: slot?.seconds,
        streaming: live,
      });
    }
    if (!end && shown[i]) {
      run ??= { kind: 'tools', key: toolKey(shown[i], i), tools: [] };
      run.tools.push(shown[i]);
    }
  }
  flush();
  return steps;
}

export function processSteps(turn, { tools, reasoning, seconds, streaming = false, hasReasoning }) {
  const spans = spanSlots(turn, Array.isArray(turn?.tools) ? turn.tools.length : 0);
  if (spans.size) return spanSteps(turn, tools, spans, streaming);
  const ordered = orderedTools(tools);
  const toolStep = ordered.length ? [{ kind: 'tools', key: toolKey(ordered[0], 0), tools: ordered }] : [];
  if (!hasReasoning) return toolStep;
  const thought = {
    kind: 'reasoning',
    key: 'r0',
    text: reasoning,
    seconds,
    streaming,
    timeline: reasoningTimeline(turn?.tools, turn?.reasoning),
  };
  return reasoningFirst(turn, ordered) ? [thought, ...toolStep] : [...toolStep, thought];
}

export function reasoningTimeline(tools, turnReasoning) {
  const list = orderedTools(tools);
  const perTool = list.map((t) => String(t.reasoning ?? '').trim());
  const trailing = trailingAfter(perTool.filter(Boolean), turnReasoning);
  const items = [];
  list.forEach((t, i) => {
    if (perTool[i]) items.push({ kind: 'text', text: perTool[i] });
    const last = items[items.length - 1];
    if (last?.kind === 'tools') last.names.push(t.name);
    else items.push({ kind: 'tools', names: [t.name] });
  });
  if (trailing) items.push({ kind: 'text', text: trailing });
  while (items.length && items[0].kind === 'tools') items.shift();
  while (items.length && items[items.length - 1].kind === 'tools') items.pop();
  return items;
}
