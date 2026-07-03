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

function isEmptyStubTurn(turn) {
  return !!turn && !(turn.assistant && turn.assistant.trim()) && (turn.tools?.length ?? 0) === 0;
}

// pendingTurn already merged in means this device is streaming it locally
export function isLastTurnInFlight(turns, sessionInFlight) {
  if (!sessionInFlight || !Array.isArray(turns) || !turns.length) return false;
  const last = turns[turns.length - 1];
  return isEmptyStubTurn(last) && !last.pending;
}

export function autoReadText(streamedReply, turns) {
  const last = Array.isArray(turns) ? turns[turns.length - 1] : null;
  return streamedReply || last?.assistant || '';
}

export function consumeAutoRead(streamedReply, autoRead, turns) {
  return { speak: autoRead ? autoReadText(streamedReply, turns) : '', nextStreamed: '' };
}
