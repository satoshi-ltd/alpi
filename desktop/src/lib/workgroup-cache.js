const KEY_PREFIX = "alpi.workgroup.cache";
const MAX_MESSAGES = 200;

function key(connectionId, profile, wgId) {
  return `${KEY_PREFIX}.${connectionId || "local"}.${profile}.${wgId}`;
}

export function loadCachedMessages(connectionId, profile, wgId) {
  try {
    const raw = localStorage.getItem(key(connectionId, profile, wgId));
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function saveCachedMessages(connectionId, profile, wgId, messages) {
  try {
    const arr = Array.isArray(messages) ? messages : [];
    const bounded = arr.length > MAX_MESSAGES ? arr.slice(-MAX_MESSAGES) : arr;
    localStorage.setItem(key(connectionId, profile, wgId), JSON.stringify(bounded));
  } catch {
    /* */
  }
}

// Drops cache entries for the given connection whose workgroups are no longer in the live list. Caches for other connections are untouched.
export function pruneCachedMessages(connectionId, liveWorkgroups) {
  if (!connectionId) return;
  try {
    const alive = new Set(
      (liveWorkgroups ?? []).map((w) => key(connectionId, w.profile, w.id)),
    );
    const scope = `${KEY_PREFIX}.${connectionId}.`;
    const toRemove = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const k = localStorage.key(i);
      if (k && k.startsWith(scope) && !alive.has(k)) toRemove.push(k);
    }
    for (const k of toRemove) localStorage.removeItem(k);
  } catch {
    /* */
  }
}
