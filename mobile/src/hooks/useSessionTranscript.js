import { useCallback, useEffect, useRef, useState } from 'react';

import { isUnfinishedStub } from '../features/chat/chatTurns';
import { useEndpoint } from '../lib/EndpointContext';

const TAIL_TURNS = 60;
const OLDER_CHUNK = 30;

const store = new Map();

export function _resetSessionTranscriptStore() {
  store.clear();
}

const EMPTY_SNAP = {
  data: null,
  turnsOffset: 0,
  totalTurns: null,
  inFlight: false,
  loading: false,
  loadingOlder: false,
  settled: true,
  error: null,
};

function entryFor(key) {
  let entry = store.get(key);
  if (!entry) {
    entry = {
      session: null,
      turnsOffset: 0,
      totalTurns: null,
      inFlight: false,
      loading: false,
      loadingOlder: false,
      settled: false,
      error: null,
      refreshing: null,
      refreshAgain: false,
      older: null,
      listeners: new Set(),
    };
    store.set(key, entry);
  }
  return entry;
}

function snapshotOf(entry) {
  return {
    data: entry.session,
    turnsOffset: entry.turnsOffset,
    totalTurns: entry.totalTurns,
    inFlight: entry.inFlight,
    loading: entry.loading,
    loadingOlder: entry.loadingOlder,
    settled: entry.settled,
    error: entry.error,
  };
}

function notify(entry) {
  const snap = snapshotOf(entry);
  for (const fn of entry.listeners) fn(snap);
}

function isAuthFailure(error) {
  const message = String(error?.message || '');
  return (
    (message === 'auth-failed' && error?.data?.reason !== 'connection-disabled') ||
    message === 'forbidden'
  );
}

const NOT_FOUND = -32004;

export function isMissingSession(error) {
  return !!error && (error.code === NOT_FOUND || String(error.message || '') === 'not-found');
}

// totalTurns null ⇒ the daemon predates slicing and shipped the full transcript.
export function normalizeSessionRead(raw) {
  if (raw && typeof raw === 'object' && !Array.isArray(raw) && 'session' in raw) {
    return {
      session: raw.session,
      totalTurns: Number.isInteger(raw.total_turns) ? raw.total_turns : null,
      turnsOffset: Number.isInteger(raw.turns_offset) ? raw.turns_offset : 0,
      inFlight: raw.in_flight === true,
    };
  }
  return { session: raw, totalTurns: null, turnsOffset: 0, inFlight: false };
}

export function fromTail(res) {
  return {
    session: res.session,
    turnsOffset: res.totalTurns == null ? 0 : res.turnsOffset,
    totalTurns: res.totalTurns,
    inFlight: res.inFlight,
  };
}

// null ⇒ the session shrank or the slice is non-contiguous (rewritten) — caller must refetch a fresh tail.
export function mergeDelta(prev, res) {
  if (res.totalTurns == null) return fromTail(res);
  const knownEnd = prev.turnsOffset + (prev.session?.turns?.length ?? 0);
  if (res.totalTurns < knownEnd || res.turnsOffset !== knownEnd) return null;
  const fresh = Array.isArray(res.session?.turns) ? res.session.turns : [];
  return {
    session: { ...prev.session, ...res.session, turns: [...prev.session.turns, ...fresh] },
    turnsOffset: prev.turnsOffset,
    totalTurns: res.totalTurns,
    inFlight: res.inFlight,
  };
}

// null ⇒ non-contiguous chunk (concurrent change) — ignore; daemons without before_turn ship the full session, which lands as the replace branch.
export function mergeOlder(prev, res) {
  if (prev.turnsOffset <= 0 || !prev.session) return null;
  const chunk = Array.isArray(res.session?.turns) ? res.session.turns : [];
  if (res.totalTurns == null || (res.turnsOffset === 0 && chunk.length >= res.totalTurns)) {
    return fromTail(res);
  }
  if (res.turnsOffset + chunk.length !== prev.turnsOffset) return null;
  return {
    session: { ...prev.session, turns: [...chunk, ...prev.session.turns] },
    turnsOffset: res.turnsOffset,
    totalTurns: res.totalTurns,
    inFlight: prev.inFlight,
  };
}

function currentState(entry) {
  return {
    session: entry.session,
    turnsOffset: entry.turnsOffset,
    totalTurns: entry.totalTurns,
    inFlight: entry.inFlight,
  };
}

function applyState(entry, next) {
  entry.session = next.session;
  entry.turnsOffset = next.turnsOffset ?? 0;
  entry.totalTurns = next.totalTurns;
  entry.inFlight = next.inFlight === true;
}

function keyFor(endpointId, profile, sessionId) {
  return endpointId && profile && sessionId ? `${endpointId}|${profile}|${sessionId}` : null;
}

function joinRefresh(entry) {
  const current = entry.refreshing;
  if (!current) return Promise.resolve(null);
  return current.then(() => joinRefresh(entry));
}

function startRefresh(entry, call, profile, sessionId) {
  // A refresh requested mid-flight must run again after: the in-flight read may predate the change that triggered it.
  if (entry.refreshing) {
    entry.refreshAgain = true;
    return joinRefresh(entry);
  }
  entry.loading = entry.session == null;
  entry.error = null;
  notify(entry);
  const knownEnd = entry.turnsOffset + (entry.session?.turns?.length ?? 0);
  // The daemon overwrites the stub in place, so after_turn=knownEnd would skip the finished turn forever.
  const useDelta = entry.session != null && entry.totalTurns != null && knownEnd > 0
    && !isUnfinishedStub(entry.session.turns?.[entry.session.turns.length - 1]);
  const params = useDelta
    ? { profile, id: sessionId, after_turn: knownEnd }
    : { profile, id: sessionId, tail_turns: TAIL_TURNS };
  const promise = call('host.session.read', params)
    .then(async (raw) => {
      const res = normalizeSessionRead(raw);
      if (useDelta) {
        const merged = mergeDelta(currentState(entry), res);
        if (merged) {
          applyState(entry, merged);
          return;
        }
        const fresh = await call('host.session.read', {
          profile, id: sessionId, tail_turns: TAIL_TURNS,
        });
        applyState(entry, fromTail(normalizeSessionRead(fresh)));
        return;
      }
      applyState(entry, fromTail(res));
    })
    .catch((e) => {
      entry.error = e;
      if (isAuthFailure(e)) {
        entry.session = null;
        entry.turnsOffset = 0;
        entry.totalTurns = null;
      }
    })
    .finally(() => {
      entry.refreshing = null;
      entry.loading = false;
      entry.settled = true;
      notify(entry);
      if (entry.refreshAgain) {
        entry.refreshAgain = false;
        startRefresh(entry, call, profile, sessionId).catch(() => {});
      }
    });
  entry.refreshing = promise;
  return promise;
}

function startOlder(entry, call, profile, sessionId) {
  if (entry.older) return entry.older;
  if (!entry.session || entry.turnsOffset <= 0) return Promise.resolve(null);
  entry.loadingOlder = true;
  notify(entry);
  const promise = call('host.session.read', {
    profile, id: sessionId, before_turn: entry.turnsOffset, max_turns: OLDER_CHUNK,
  })
    .then((raw) => {
      const merged = mergeOlder(currentState(entry), normalizeSessionRead(raw));
      if (merged) applyState(entry, merged);
    })
    .catch((e) => {
      entry.error = e;
    })
    .finally(() => {
      entry.older = null;
      entry.loadingOlder = false;
      notify(entry);
    });
  entry.older = promise;
  return promise;
}

export function useSessionTranscript(profile, sessionId) {
  const { endpoint, call } = useEndpoint();
  const key = keyFor(endpoint?.id, profile, sessionId);

  const [snap, setSnap] = useState(() => (key ? snapshotOf(entryFor(key)) : EMPTY_SNAP));
  // reset snap synchronously on key flip — else one render bleeds the previous session's data
  const [trackedKey, setTrackedKey] = useState(key);
  if (trackedKey !== key) {
    setTrackedKey(key);
    setSnap(key ? snapshotOf(entryFor(key)) : EMPTY_SNAP);
  }

  const keyRef = useRef(key);
  keyRef.current = key;

  useEffect(() => {
    if (!key) return undefined;
    const entry = entryFor(key);
    const listener = (s) => {
      if (keyRef.current === key) setSnap(s);
    };
    entry.listeners.add(listener);
    setSnap(snapshotOf(entry));
    startRefresh(entry, call, profile, sessionId).catch(() => {});
    return () => {
      entry.listeners.delete(listener);
    };
  }, [key, call]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useCallback((targetSessionId) => {
    const sid = targetSessionId || sessionId;
    const target = keyFor(endpoint?.id, profile, sid);
    if (!target) return Promise.resolve(null);
    const entry = entryFor(target);
    return startRefresh(entry, call, profile, sid)
      .then(() => snapshotOf(entry))
      .catch(() => null);
  }, [key, call]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadOlder = useCallback(() => {
    if (!key) return Promise.resolve(null);
    return startOlder(entryFor(key), call, profile, sessionId).catch(() => null);
  }, [key, call]); // eslint-disable-line react-hooks/exhaustive-deps

  return { ...snap, hasMore: snap.turnsOffset > 0, refresh, loadOlder };
}
