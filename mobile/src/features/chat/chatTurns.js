export function mergeStreamingTurn(turns, pendingTurn) {
  if (!pendingTurn) return turns;
  const out = Array.isArray(turns) ? [...turns] : [];
  const lastIdx = out.length - 1;
  const last = out[lastIdx];
  if (last && last.user === pendingTurn.user && !last.assistant) {
    out[lastIdx] = { ...last, ...pendingTurn };
    return out;
  }
  out.push(pendingTurn);
  return out;
}

export function isInterruptedTurn(turn) {
  return !!turn?.unfinished && !turn?.pending;
}

export function autoReadText(streamedReply, turns) {
  const last = Array.isArray(turns) ? turns[turns.length - 1] : null;
  return streamedReply || last?.assistant || '';
}

export function consumeAutoRead(streamedReply, autoRead, turns) {
  return { speak: autoRead ? autoReadText(streamedReply, turns) : '', nextStreamed: '' };
}
