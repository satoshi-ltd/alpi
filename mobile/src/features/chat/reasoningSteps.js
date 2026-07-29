function num(v) {
  return typeof v === 'number' && Number.isFinite(v) ? v : NaN;
}

export function turnParts(turn) {
  const all = Array.isArray(turn?.tools) ? turn.tools : [];
  const tools = all.filter((t) => t.name !== 'ask_user');
  const askUsers = all
    .filter((t) => t.name === 'ask_user')
    .map((t) => ({
      tool_id: t.tool_id,
      question: t.args?.question ?? '',
      result: String(t.output ?? t.result ?? '').trim(),
    }))
    .filter((a) => a.result);
  const reasoning = consolidateReasoning(all, turn?.reasoning);
  const seconds = num(turn?.reasoned_s);
  return {
    tools,
    askUsers,
    reasoning,
    reasonedSeconds: Number.isFinite(seconds) ? seconds : undefined,
  };
}

// strip per-tool segments already inside the persisted join, else persisted turns double-render them
function consolidateReasoning(tools, turnReasoning) {
  const perTool = tools.map((t) => String(t.reasoning ?? '').trim()).filter(Boolean);
  let trailing = String(turnReasoning ?? '').trim();
  for (const seg of perTool) {
    const rest = trailing.replace(/^\s+/, '');
    if (rest.startsWith(seg)) trailing = rest.slice(seg.length);
    else break;
  }
  return [...perTool, trailing.trim()].filter(Boolean).join('\n\n');
}
