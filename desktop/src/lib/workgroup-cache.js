const KEY_PREFIX = "alpi.workgroup.cache";

function key(profile, wgId) {
  return `${KEY_PREFIX}.${profile}.${wgId}`;
}

export function loadCachedMessages(profile, wgId) {
  try {
    const raw = localStorage.getItem(key(profile, wgId));
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function saveCachedMessages(profile, wgId, messages) {
  try {
    localStorage.setItem(key(profile, wgId), JSON.stringify(messages));
  } catch {
    /* best-effort cache: quota or serialization — ignore */
  }
}
