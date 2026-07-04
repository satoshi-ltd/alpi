const KEY_PREFIX = "alpi.session.cache.v1";
const MAX_PERSISTED_TURNS = 60;
const MIN_PERSISTED_TURNS = 4;
const MAX_SESSIONS_PER_SCOPE = 8;
const MAX_PERSIST_BYTES = 400_000;
const TEXT_PERSIST_CAP = 16_000;
const TOOL_OUTPUT_PERSIST_CAP = 4_000;

// Memory holds the server-sourced session (full, or a contiguous slice with turnsOffset); localStorage holds a trimmed tail marked partialTail+displayOnly — turnsOffset kept for absolute indices, displayOnly bars it from the after_turn delta path.
const _memory = new Map();

function key(connectionId, profile, sessionId) {
  return `${KEY_PREFIX}.${connectionId || "local"}.${profile}.${sessionId}`;
}

function indexKey(connectionId, profile) {
  return `${KEY_PREFIX}.index.${connectionId || "local"}.${profile}`;
}

export function loadCachedSession(connectionId, profile, sessionId) {
  const k = key(connectionId, profile, sessionId);
  if (_memory.has(k)) {
    const data = _memory.get(k);
    return { data, complete: !data?.partialTail };
  }
  try {
    const raw = localStorage.getItem(k);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data !== "object" || !Array.isArray(data.turns)) return null;
    return { data, complete: false };
  } catch {
    return null;
  }
}

function clip(s, cap) {
  return typeof s === "string" && s.length > cap ? `${s.slice(0, cap)}…` : s;
}

function trimTurnForPersist(turn) {
  if (!turn || typeof turn !== "object") return turn;
  const out = { ...turn };
  out.user = clip(out.user, TEXT_PERSIST_CAP);
  out.assistant = clip(out.assistant, TEXT_PERSIST_CAP);
  out.reasoning = clip(out.reasoning, TEXT_PERSIST_CAP);
  if (Array.isArray(out.tools)) {
    out.tools = out.tools.map((t) =>
      t && typeof t === "object" ? { ...t, output: clip(t.output, TOOL_OUTPUT_PERSIST_CAP) } : t,
    );
  }
  return out;
}

export function saveCachedSession(connectionId, profile, sessionId, data, { persist = true } = {}) {
  if (!data || typeof data !== "object" || !Array.isArray(data.turns)) return;
  const k = key(connectionId, profile, sessionId);
  _memory.set(k, data);
  if (!persist) return;
  try {
    const absoluteEnd = (Number.isInteger(data.turnsOffset) ? data.turnsOffset : 0) + data.turns.length;
    let turns = data.turns.slice(-MAX_PERSISTED_TURNS).map(trimTurnForPersist);
    // displayOnly keeps a persisted tail out of the after_turn delta path; turnsOffset stays so rewrite/retry indices remain absolute while it is on screen.
    const tail = { ...data, partialTail: true, displayOnly: true };
    delete tail.totalTurns;
    let serialized;
    for (;;) {
      tail.turns = turns;
      tail.turnsOffset = absoluteEnd - turns.length;
      serialized = JSON.stringify(tail);
      if (serialized.length <= MAX_PERSIST_BYTES) break;
      if (turns.length <= MIN_PERSISTED_TURNS) return;
      turns = turns.slice(Math.ceil(turns.length / 2));
    }
    localStorage.setItem(k, serialized);
    touchIndex(connectionId, profile, sessionId);
  } catch {
    /* quota — memory cache still holds it */
  }
}

function touchIndex(connectionId, profile, sessionId) {
  const ik = indexKey(connectionId, profile);
  let ids = [];
  try {
    const raw = localStorage.getItem(ik);
    const parsed = raw ? JSON.parse(raw) : [];
    ids = Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    ids = [];
  }
  ids = ids.filter((id) => id !== sessionId);
  ids.push(sessionId);
  const evicted = ids.length > MAX_SESSIONS_PER_SCOPE ? ids.splice(0, ids.length - MAX_SESSIONS_PER_SCOPE) : [];
  try {
    localStorage.setItem(ik, JSON.stringify(ids));
    for (const id of evicted) localStorage.removeItem(key(connectionId, profile, id));
  } catch {}
}

export function removeCachedSession(connectionId, profile, sessionId) {
  _memory.delete(key(connectionId, profile, sessionId));
  try {
    localStorage.removeItem(key(connectionId, profile, sessionId));
  } catch {}
}

// Memory-only: persisted tails stay (they are revalidated on open anyway).
export function invalidateSessionCache(connectionId) {
  const prefix = `${KEY_PREFIX}.${connectionId || "local"}.`;
  for (const k of Array.from(_memory.keys())) {
    if (k.startsWith(prefix)) _memory.delete(k);
  }
}

// Test-only.
export function _clearSessionCache() {
  _memory.clear();
}
