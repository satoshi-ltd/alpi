export function pendingTurnForView({ pendingTurns, view, activeProfileName }) {
  if (!pendingTurns || !activeProfileName) return null;
  const viewSessionId = view?.kind === "profile" ? (view.sessionId ?? null) : null;
  let exact = null;
  let newChat = null;
  for (const turn of Object.values(pendingTurns)) {
    if (turn.profile !== activeProfileName) continue;
    if ((turn.sessionId ?? null) === viewSessionId) {
      exact = turn;
      continue;
    }
    // New chat keeps streaming in its composer: the view's sessionId lags the real id (set on `reply`), so match the frozen launch slot instead.
    if (viewSessionId === null && (turn.launchSessionId ?? null) === null) {
      if (!newChat || (turn.at ?? 0) > (newChat.at ?? 0)) newChat = turn;
    }
  }
  return exact ?? newChat;
}
