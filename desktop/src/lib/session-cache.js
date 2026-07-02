const KEY_PREFIX = "alpi.session.cache.v1";
const MAX_PERSISTED_TURNS = 60;
const MAX_SESSIONS_PER_SCOPE = 8;
const MAX_PERSIST_BYTES = 400_000;

// Memory holds the FULL session (safe as `known` for incremental fetch); localStorage holds a tail marked partialTail so it is never used as an after_turn base.
const _memory = new Map();

function key(connectionId, profile, sessionId) {
  return `${KEY_PREFIX}.${connectionId || "local"}.${profile}.${sessionId}`;
}

function indexKey(connectionId, profile) {
  return `${KEY_PREFIX}.index.${connectionId || "local"}.${profile}`;
}

export function loadCachedSession(connectionId, profile, sessionId) {
  const k = key(connectionId, profile, sessionId);
  if (_memory.has(k)) return { data: _memory.get(k), complete: true };
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

export function saveCachedSession(connectionId, profile, sessionId, data) {
  if (!data || typeof data !== "object" || !Array.isArray(data.turns)) return;
  const k = key(connectionId, profile, sessionId);
  _memory.set(k, data);
  try {
    const tail = {
      ...data,
      turns: data.turns.slice(-MAX_PERSISTED_TURNS),
      partialTail: true,
    };
    const serialized = JSON.stringify(tail);
    if (serialized.length > MAX_PERSIST_BYTES) return;
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
