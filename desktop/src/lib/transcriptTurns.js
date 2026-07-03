function isEmptyStubTurn(turn) {
  return !!turn && !(turn.assistant && turn.assistant.trim()) && (turn.tools?.length ?? 0) === 0;
}

// drop the in-flight stub turn — pendingTurn already renders it
export function dropInflightStub(turns, pendingTurn) {
  if (!pendingTurn || !turns.length) return turns;
  const last = turns[turns.length - 1];
  const isStub = isEmptyStubTurn(last) && last.user === pendingTurn.user;
  return isStub ? turns.slice(0, -1) : turns;
}

// caller must have already dropped the stub if a local pendingTurn covers it
export function isLastTurnInFlight(turns, sessionInFlight) {
  if (!sessionInFlight || !turns.length) return false;
  return isEmptyStubTurn(turns[turns.length - 1]);
}
