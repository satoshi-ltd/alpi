const KEY_PREFIX = "alpi.workgroup.cache";
const MAX_MESSAGES = 200;
const SAVE_DEBOUNCE_MS = 1000;

// Pending debounced writes keyed by storage key — loadCachedMessages reads through them so callers never observe the debounce.
const _pendingSaves = new Map();

function key(connectionId, profile, wgId) {
  return `${KEY_PREFIX}.${connectionId || "local"}.${profile}.${wgId}`;
}

export function loadCachedMessages(connectionId, profile, wgId) {
  const k = key(connectionId, profile, wgId);
  const pending = _pendingSaves.get(k);
  if (pending) return pending.value;
  try {
    const raw = localStorage.getItem(k);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

// Trailing debounce keeps the synchronous JSON.stringify + localStorage write off the per-post hot path.
export function saveCachedMessages(connectionId, profile, wgId, messages) {
  const arr = Array.isArray(messages) ? messages : [];
  const bounded = arr.length > MAX_MESSAGES ? arr.slice(-MAX_MESSAGES) : arr;
  const k = key(connectionId, profile, wgId);
  const pending = _pendingSaves.get(k);
  if (pending) clearTimeout(pending.timer);
  const timer = setTimeout(() => {
    _pendingSaves.delete(k);
    try {
      localStorage.setItem(k, JSON.stringify(bounded));
    } catch {
      /* */
    }
  }, SAVE_DEBOUNCE_MS);
  _pendingSaves.set(k, { timer, value: bounded });
}

// Test-only.
export function _resetPendingSaves() {
  for (const { timer } of _pendingSaves.values()) clearTimeout(timer);
  _pendingSaves.clear();
}

// Drops cache entries for the given connection whose workgroups are no longer in the live list. Caches for other connections are untouched.
export function pruneCachedMessages(connectionId, liveWorkgroups) {
  if (!connectionId) return;
  try {
    const alive = new Set(
      (liveWorkgroups ?? []).map((w) => key(connectionId, w.profile, w.id)),
    );
    const scope = `${KEY_PREFIX}.${connectionId}.`;
    for (const [k, pending] of Array.from(_pendingSaves)) {
      if (k.startsWith(scope) && !alive.has(k)) {
        clearTimeout(pending.timer);
        _pendingSaves.delete(k);
      }
    }
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
