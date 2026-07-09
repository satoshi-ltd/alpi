const STORAGE_KEY = "alpi.session.titles.v1";
export const SESSION_TITLE_MAX = 120;
export const SESSION_TITLE_CHANGED = "alpi:session-title-changed";

function safeRead() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function safeWrite(titles) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(titles));
  } catch {
    return false;
  }
  return true;
}

function emitChanged(detail) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(SESSION_TITLE_CHANGED, { detail }));
}

export function normalizeSessionTitle(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim().slice(0, SESSION_TITLE_MAX);
}

export function sessionTitleKey(connectionId, profile, sessionId) {
  if (!profile || !sessionId) return null;
  return `${connectionId || "local"}|${profile}|${sessionId}`;
}

export function baseSessionTitle(session, max = Infinity) {
  const t = String(session?.first_user ?? "").trim();
  const title = t || `(empty · ${String(session?.id ?? "").slice(0, 6)})`;
  return truncateSessionTitle(title, max);
}

export function truncateSessionTitle(title, max = Infinity) {
  const text = String(title ?? "");
  if (!Number.isFinite(max) || max <= 0 || text.length <= max) return text;
  return `${text.slice(0, max)}…`;
}

export function getSessionTitle(connectionId, profile, sessionId) {
  const key = sessionTitleKey(connectionId, profile, sessionId);
  if (!key) return "";
  const value = safeRead()[key];
  return typeof value === "string" ? value : "";
}

export function setSessionTitle(connectionId, profile, sessionId, value) {
  const key = sessionTitleKey(connectionId, profile, sessionId);
  if (!key) return "";
  const title = normalizeSessionTitle(value);
  const titles = safeRead();
  if (title) titles[key] = title;
  else delete titles[key];
  if (safeWrite(titles)) emitChanged({ connectionId: connectionId || null, profile, sessionId, title });
  return title;
}

export function removeSessionTitles(connectionId, profile, sessionIds = []) {
  const titles = safeRead();
  let changed = false;
  for (const sessionId of sessionIds) {
    const key = sessionTitleKey(connectionId, profile, sessionId);
    if (key && Object.hasOwn(titles, key)) {
      delete titles[key];
      changed = true;
    }
  }
  if (changed && safeWrite(titles)) emitChanged({ connectionId: connectionId || null, profile, sessionIds, title: "" });
  return changed;
}

export function purgeConnectionSessionTitles(connectionId) {
  if (!connectionId || connectionId === "local") return false;
  const prefix = `${connectionId}|`;
  const titles = safeRead();
  let changed = false;
  for (const key of Object.keys(titles)) {
    if (key.startsWith(prefix)) {
      delete titles[key];
      changed = true;
    }
  }
  if (changed && safeWrite(titles)) emitChanged({ connectionId, title: "" });
  return changed;
}

export function displaySessionTitle(session, { connectionId = null, profile = null, max = Infinity } = {}) {
  const title = getSessionTitle(connectionId, profile, session?.id);
  return truncateSessionTitle(title || baseSessionTitle(session), max);
}

export function editableSessionTitle(session, { connectionId = null, profile = null } = {}) {
  return getSessionTitle(connectionId, profile, session?.id) || String(session?.first_user ?? "").trim();
}

export function subscribeSessionTitles(listener) {
  if (typeof window === "undefined") return () => {};
  const onStorage = (event) => {
    if (!event.key || event.key === STORAGE_KEY) listener(event);
  };
  window.addEventListener(SESSION_TITLE_CHANGED, listener);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(SESSION_TITLE_CHANGED, listener);
    window.removeEventListener("storage", onStorage);
  };
}
