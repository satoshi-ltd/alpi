import {
  fetchFullSession,
  fetchSessionDetail,
  isDeltaBase,
  isSessionGone,
} from "./session-fetch.js";
import { loadCachedSession, saveCachedSession } from "./session-cache.js";

const TAIL_TURNS = 60;
const BACKFILL_CHUNK_TURNS = 100;

export function sessionFromSlice(res) {
  const data = { ...res.session, in_flight: res.inFlight };
  if (res.kind != null) data.kind = res.kind;
  if (res.totalTurns != null) {
    data.totalTurns = res.totalTurns;
    if (res.turnsOffset > 0) {
      data.turnsOffset = res.turnsOffset;
      data.partialTail = true;
    }
  }
  return data;
}

export function prependOlderTurns(prev, res) {
  if (!prev || !Array.isArray(prev.turns)) return { data: prev, action: "skip" };
  const prevOffset = Number.isInteger(prev.turnsOffset) ? prev.turnsOffset : 0;
  if (prevOffset <= 0) return { data: prev, action: "skip" };
  const chunk = Array.isArray(res.session?.turns) ? res.session.turns : [];
  if (res.totalTurns == null || (res.turnsOffset === 0 && chunk.length >= res.totalTurns)) {
    return { data: sessionFromSlice(res), action: "replace" };
  }
  if (res.totalTurns < prevOffset + prev.turns.length) {
    return { data: prev, action: "restart" };
  }
  if (res.turnsOffset + chunk.length !== prevOffset) return { data: prev, action: "skip" };
  const data = { ...prev, turns: [...chunk, ...prev.turns], totalTurns: res.totalTurns };
  if (res.turnsOffset > 0) {
    data.turnsOffset = res.turnsOffset;
  } else {
    delete data.turnsOffset;
    delete data.partialTail;
  }
  return { data, action: "applied" };
}

export function createSessionOpener({
  activeConnectionIdRef,
  sessionDataRef = null,
  setSessionData,
  setSessionSync,
  isChatSessionData,
  onGone,
  onNonChat,
  onError = null,
  fetchDetail = fetchSessionDetail,
  fetchFull = fetchFullSession,
  loadCached = loadCachedSession,
  saveCached = saveCachedSession,
}) {
  function open(profile, sessionId) {
    const connId = activeConnectionIdRef.current;
    let cancelled = false;
    const live = () => !cancelled && activeConnectionIdRef.current === connId;
    const sync = (s) => {
      if (live()) setSessionSync(s);
    };

    const cached = loadCached(connId, profile, sessionId);
    setSessionData(cached?.data ?? null);

    async function backfill(startData) {
      let cur = startData;
      for (;;) {
        // Adopt the rendered state each round: a concurrent refresh/finish-turn replace would otherwise desync the loop and strand the view partial.
        const liveData = sessionDataRef?.current;
        if (liveData && liveData.id === sessionId && Array.isArray(liveData.turns)) cur = liveData;
        if (!live() || !cur || cur.id !== sessionId) return;
        const offset = Number.isInteger(cur.turnsOffset) ? cur.turnsOffset : 0;
        if (offset <= 0) {
          saveCached(connId, profile, sessionId, cur);
          return;
        }
        const res = await fetchDetail(profile, sessionId, {
          beforeTurn: offset,
          maxTurns: BACKFILL_CHUNK_TURNS,
        });
        if (!live()) return;
        const r = prependOlderTurns(cur, res);
        if (r.action === "restart") {
          const data = await fetchFull(profile, sessionId);
          if (!live()) return;
          saveCached(connId, profile, sessionId, data);
          setSessionData(data);
          return;
        }
        if (r.action === "skip") return;
        cur = r.data;
        saveCached(connId, profile, sessionId, cur, { persist: false });
        // Re-derive against the true prev so concurrent delta-appends at the tail are never clobbered.
        setSessionData((prev) => {
          const rr = prependOlderTurns(prev, res);
          return rr.action === "applied" || rr.action === "replace" ? rr.data : prev;
        });
      }
    }

    (async () => {
      try {
        let data;
        if (cached?.data && isDeltaBase(cached.data) && cached.data.id === sessionId && cached.data.turns.length > 0) {
          sync({ phase: "refresh" });
          data = await fetchFull(profile, sessionId, { known: cached.data });
        } else {
          sync({ phase: "refresh" });
          const res = await fetchDetail(profile, sessionId, { tailTurns: TAIL_TURNS });
          data = sessionFromSlice(res);
        }
        if (!live()) return;
        if (!isChatSessionData(data)) {
          sync(null);
          onNonChat?.(connId, profile, sessionId);
          return;
        }
        saveCached(connId, profile, sessionId, data);
        setSessionData(data);
        // The bar tracks what the user sees: once the tail is live it goes dark; history backfill continues silently.
        sync(null);
        await backfill(data);
      } catch (e) {
        sync(null);
        if (isSessionGone(e)) {
          if (live()) onGone?.(connId, profile, sessionId);
          return;
        }
        if (live()) onError?.(e);
      }
    })();

    return () => {
      cancelled = true;
    };
  }

  return { open };
}
