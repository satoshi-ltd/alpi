import { invoke } from "@tauri-apps/api/core";

export function normalizeSessionResult(raw) {
  if (raw && typeof raw === "object" && !Array.isArray(raw) && "session" in raw) {
    return {
      session: raw.session,
      totalTurns: Number.isInteger(raw.total_turns) ? raw.total_turns : null,
      turnsOffset: Number.isInteger(raw.turns_offset) ? raw.turns_offset : 0,
      inFlight: raw.in_flight === true,
      kind: typeof raw.kind === "string" ? raw.kind : null,
    };
  }
  return { session: raw, totalTurns: null, turnsOffset: 0, inFlight: false, kind: null };
}

// Delta-safe = server-sourced contiguous turns; a persisted localStorage tail is displayOnly and must never be a slice base.
export function isDeltaBase(known) {
  return !!known && Array.isArray(known.turns) && known.displayOnly !== true
    && (!known.partialTail || Number.isInteger(known.turnsOffset));
}

export function absoluteEnd(known) {
  const base = Number.isInteger(known?.turnsOffset) ? known.turnsOffset : 0;
  return base + (known?.turns?.length ?? 0);
}

export function mergeSessionTurns(known, res) {
  const knownEnd = absoluteEnd(known);
  if (res.totalTurns == null) return null;
  if (res.totalTurns < knownEnd || res.turnsOffset !== knownEnd) return null;
  const fresh = Array.isArray(res.session?.turns) ? res.session.turns : [];
  const merged = { ...known, ...res.session, turns: [...known.turns, ...fresh] };
  if (Number.isInteger(known?.turnsOffset)) merged.turnsOffset = known.turnsOffset;
  merged.totalTurns = res.totalTurns;
  return merged;
}

// -32004 only — "method-not-found" (-32601) also contains "not-found" and must NOT count.
export function isSessionGone(err) {
  const msg = String(err);
  return msg.includes("-32004") || msg.includes("auth-failed");
}

export async function fetchSessionDetail(
  profile,
  sessionId,
  { afterTurn = null, tailTurns = null, beforeTurn = null, maxTurns = null } = {},
) {
  const raw = await invoke("session_detail", {
    profile,
    id: sessionId,
    ...(afterTurn != null ? { afterTurn } : {}),
    ...(tailTurns != null ? { tailTurns } : {}),
    ...(beforeTurn != null ? { beforeTurn } : {}),
    ...(maxTurns != null ? { maxTurns } : {}),
  });
  return normalizeSessionResult(raw);
}

export async function fetchFullSession(profile, sessionId, { known = null } = {}) {
  const usable = isDeltaBase(known) && known.id === sessionId;
  if (usable && known.turns.length > 0) {
    const res = await fetchSessionDetail(profile, sessionId, {
      afterTurn: absoluteEnd(known),
    });
    if (res.totalTurns == null) return withEnvelope(res.session, res);
    const merged = mergeSessionTurns(known, res);
    if (merged) return withEnvelope(merged, res);
  }
  const res = await fetchSessionDetail(profile, sessionId);
  return withEnvelope(res.session, res);
}

function withEnvelope(session, res) {
  const out = { ...session, in_flight: res.inFlight };
  if (res.kind != null) out.kind = res.kind;
  return out;
}
