// drop the in-flight stub turn — pendingTurn already renders it
export function dropInflightStub(turns, pendingTurn) {
  if (!pendingTurn || !turns.length) return turns;
  const last = turns[turns.length - 1];
  const isStub =
    last &&
    !(last.assistant && last.assistant.trim()) &&
    (last.tools?.length ?? 0) === 0 &&
    last.user === pendingTurn.user;
  return isStub ? turns.slice(0, -1) : turns;
}
