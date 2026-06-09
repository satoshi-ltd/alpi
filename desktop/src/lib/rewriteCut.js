// pendingTurn wins over rewriteDraft: rewriteDraft is cleared on submit, so the in-flight turn is the reliable cut.
export function rewriteCut({ pendingTurn, rewriteDraft, profileName, sessionId }) {
  const match = (o) => o && o.profile === profileName && o.sessionId === sessionId;
  if (match(pendingTurn) && Number.isInteger(pendingTurn.rewriteFromTurn)) {
    return pendingTurn.rewriteFromTurn;
  }
  if (match(rewriteDraft) && Number.isInteger(rewriteDraft.turnIndex)) {
    return rewriteDraft.turnIndex;
  }
  return null;
}
