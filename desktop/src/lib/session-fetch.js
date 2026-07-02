import { invoke } from "@tauri-apps/api/core";

export function normalizeSessionResult(raw) {
  if (raw && typeof raw === "object" && !Array.isArray(raw) && "session" in raw) {
    return {
      session: raw.session,
      totalTurns: Number.isInteger(raw.total_turns) ? raw.total_turns : null,
      turnsOffset: Number.isInteger(raw.turns_offset) ? raw.turns_offset : 0,
    };
  }
  return { session: raw, totalTurns: null, turnsOffset: 0 };
}

export function mergeSessionTurns(known, res) {
  const knownTurns = known?.turns?.length ?? 0;
  if (res.totalTurns == null) return null;
  if (res.totalTurns < knownTurns || res.turnsOffset !== knownTurns) return null;
  const fresh = Array.isArray(res.session?.turns) ? res.session.turns : [];
  return { ...known, ...res.session, turns: [...known.turns, ...fresh] };
}

// -32004 only — "method-not-found" (-32601) also contains "not-found" and must NOT count.
export function isSessionGone(err) {
  const msg = String(err);
  return msg.includes("-32004") || msg.includes("auth-failed");
}

async function fetchSessionDetail(profile, sessionId, { afterTurn = null } = {}) {
  const raw = await invoke("session_detail", {
    profile,
    id: sessionId,
    ...(afterTurn != null ? { afterTurn } : {}),
  });
  return normalizeSessionResult(raw);
}

// `known` must be a FULL session (never a persisted partialTail) — its turn count becomes the daemon's slice base.
export async function fetchFullSession(profile, sessionId, { known = null } = {}) {
  const usable =
    known && !known.partialTail && known.id === sessionId && Array.isArray(known.turns);
  if (usable && known.turns.length > 0) {
    const res = await fetchSessionDetail(profile, sessionId, {
      afterTurn: known.turns.length,
    });
    if (res.totalTurns == null) return res.session;
    const merged = mergeSessionTurns(known, res);
    if (merged) return merged;
  }
  const res = await fetchSessionDetail(profile, sessionId);
  return res.session;
}
