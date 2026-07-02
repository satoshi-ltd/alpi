import { fetchFullSession, isSessionGone } from "./session-fetch.js";
import { saveCachedSession, removeCachedSession } from "./session-cache.js";

// Every side effect is keyed to the connection captured at REQUEST time — a late response from connection A must never mutate what connection B is showing.
export function createSessionRefresher({
  activeConnectionIdRef,
  sessionDataRef,
  setSessionData,
  clearViewSession,
  isChatSessionData,
}) {
  function dropDeadSession(connId, profile, sessionId) {
    removeCachedSession(connId, profile, sessionId);
    if (activeConnectionIdRef.current !== connId) return;
    setSessionData((cur) => (cur?.id === sessionId ? null : cur));
    clearViewSession(profile, sessionId);
  }

  async function refresh(profile, sessionId) {
    const connId = activeConnectionIdRef.current;
    const current = sessionDataRef.current;
    const known = current?.id === sessionId ? current : null;
    try {
      const data = await fetchFullSession(profile, sessionId, { known });
      if (!isChatSessionData(data)) return;
      saveCachedSession(connId, profile, sessionId, data);
      if (activeConnectionIdRef.current !== connId) return;
      setSessionData(data);
    } catch (e) {
      if (isSessionGone(e)) dropDeadSession(connId, profile, sessionId);
    }
  }

  return { refresh, dropDeadSession };
}
