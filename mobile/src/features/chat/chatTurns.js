import { modelLabel } from '../../lib/modelLabel';

export function mergeStreamingTurn(turns, pendingTurn) {
  if (!pendingTurn) return turns;
  const out = Array.isArray(turns) ? [...turns] : [];
  const lastIdx = out.length - 1;
  const last = out[lastIdx];
  if (last && last.user === pendingTurn.user && isUnfinishedStub(last)) {
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

// The daemon writes this stub when a turn STARTS and overwrites it in place when the turn ends.
export function isUnfinishedStub(turn) {
  return isEmptyStubTurn(turn) && !((turn?.ended_at ?? 0) > 0);
}

export function turnFrontier(snap) {
  const turns = Array.isArray(snap?.data?.turns) ? snap.data.turns : [];
  const last = turns[turns.length - 1];
  const offset = Number.isInteger(snap?.turnsOffset) ? snap.turnsOffset : 0;
  const endedAt = Number(last?.ended_at);
  return {
    count: Number.isInteger(snap?.totalTurns) ? snap.totalTurns : offset + turns.length,
    endedAt: endedAt > 0 ? endedAt : 0,
  };
}

export function turnLandedSince(snap, baseline) {
  if (!snap?.data || !baseline) return false;
  const turns = Array.isArray(snap.data.turns) ? snap.data.turns : [];
  const last = turns[turns.length - 1];
  if (!last || isUnfinishedStub(last)) return false;
  const now = turnFrontier(snap);
  return now.count !== baseline.count || now.endedAt > baseline.endedAt;
}

// pendingTurn already merged in means this device is streaming it locally
export function isLastTurnInFlight(turns, sessionInFlight) {
  if (!sessionInFlight || !Array.isArray(turns) || !turns.length) return false;
  const last = turns[turns.length - 1];
  return isEmptyStubTurn(last) && !last.pending;
}

// session model beats profile default: a model swap must not repaint history as routed
export function baselineModelFor(sessionData, profileModel) {
  return sessionData?.model || profileModel || null;
}

export function routedModelFor(turn, baselineModel) {
  const model = turn?.model;
  if (!model || !baselineModel || model === baselineModel) return null;
  return modelLabel(model);
}

export function autoReadText(streamedReply, turns) {
  const last = Array.isArray(turns) ? turns[turns.length - 1] : null;
  return streamedReply || last?.assistant || '';
}

export function consumeAutoRead(streamedReply, autoRead, turns) {
  return { speak: autoRead ? autoReadText(streamedReply, turns) : '', nextStreamed: '' };
}
