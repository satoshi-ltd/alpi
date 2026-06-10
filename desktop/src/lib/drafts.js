const KEY = "alpi.drafts.v1";
const MAX_DRAFTS = 50;

function loadAll() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "{}");
    return raw && typeof raw === "object" ? raw : {};
  } catch {
    return {};
  }
}

function persist(all) {
  try {
    localStorage.setItem(KEY, JSON.stringify(all));
  } catch {}
}

export function getDraft(key) {
  if (!key) return "";
  return loadAll()[key]?.text || "";
}

export function setDraft(key, text) {
  if (!key) return;
  const all = loadAll();
  if (!text || !text.trim()) {
    delete all[key];
  } else {
    all[key] = { text, at: Date.now() };
    const keys = Object.keys(all);
    if (keys.length > MAX_DRAFTS) {
      keys
        .sort((a, b) => (all[a].at || 0) - (all[b].at || 0))
        .slice(0, keys.length - MAX_DRAFTS)
        .forEach((k) => delete all[k]);
    }
  }
  persist(all);
}

export function clearDraft(key) {
  if (!key) return;
  const all = loadAll();
  if (key in all) {
    delete all[key];
    persist(all);
  }
}
