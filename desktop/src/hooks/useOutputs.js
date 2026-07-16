import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { subscribeDaemonEvent } from "../lib/daemon-bus.js";

const DEFAULT_LIMIT = 100;

// In-process bus so a mark_read in one hook instance refreshes siblings (modal list + sidebar badge) before the daemon round-trips output.updated.
const _localListeners = new Set();
function notifyLocalChange(connectionId = null) {
  for (const fn of _localListeners) {
    try { fn(connectionId); } catch { /* */ }
  }
}

const OTHERS_DEFER_MS = 4000;
const OTHERS_STAGGER_MS = 400;
const OPEN_MAX_CONCURRENT = 6;

// Last fetched rows per connection+credential+filter, surviving unmounts: a reopened inbox paints instantly, then revalidates.
const _rowsMemory = new Map();

// token_id in the key: remote ids are deterministic per host:port, so re-pairing the same endpoint with new credentials must never surface the old credential's rows.
function _memoryKey(connectionId, authId, statusKey) {
  return `${connectionId}|${authId}|${statusKey}`;
}

function _authId(conn) {
  return String(conn?.token_id ?? "");
}

export function _resetOutputsMemory() {
  _rowsMemory.clear();
}

export function purgeOutputsMemory(connectionId) {
  for (const key of Array.from(_rowsMemory.keys())) {
    if (key.startsWith(`${connectionId}|`)) _rowsMemory.delete(key);
  }
}


// Returns rows, or null when the daemon could not be asked (network failure) — null must never clobber last-known rows.
export async function fetchConnectionOutputs(connection, status, previous = null) {
  const connectionId = connection?.id;
  if (!connectionId) return null;
  let profiles;
  try {
    const res = await invoke("profile_summaries", { connectionId });
    profiles = (Array.isArray(res) ? res : []).map((p) => ({ name: p.name, accent: p.accent || null, voice_id: p.voice_id ?? null }));
  } catch {
    return null;
  }
  if (profiles.length === 0) profiles = [{ name: "default", accent: null }];

  // A reply without `aggregate: true` = pre-aggregate daemon (fan out below); a rejection = unreachable, never legacy — falling back there would burn one call per profile.
  let aggregated;
  try {
    aggregated = await invoke("outputs_list", {
      profile: "",
      all: true,
      ...(status ? { status } : {}),
      limit: DEFAULT_LIMIT,
      connectionId,
    });
  } catch {
    return null;
  }
  if (aggregated?.aggregate === true && Array.isArray(aggregated.outputs)) {
    const byName = new Map(profiles.map((p) => [p.name, p]));
    return aggregated.outputs.map((o) => {
      const p = byName.get(o.profile) ?? {};
      return {
        ...o,
        profile: o.profile || "default",
        accent: p.accent ?? null,
        voice_id: p.voice_id ?? null,
        connectionId,
        connectionName: connection.name,
      };
    });
  }

  const lists = await Promise.all(
    profiles.map((p) =>
      invoke("outputs_list", {
        profile: p.name,
        ...(status ? { status } : {}),
        limit: DEFAULT_LIMIT,
        connectionId,
      })
        .then((res) =>
          (Array.isArray(res) ? res : []).map((o) => ({
            ...o,
            profile: o.profile || p.name,
            accent: p.accent,
            voice_id: p.voice_id,
            connectionId,
            connectionName: connection.name,
          })),
        )
        .catch(() => null),
    ),
  );
  if (lists.length > 0 && lists.every((r) => r === null)) return null;
  const rows = [];
  for (let i = 0; i < profiles.length; i += 1) {
    const fetched = lists[i];
    if (fetched === null) {
      if (Array.isArray(previous)) {
        rows.push(...previous.filter((row) => row.profile === profiles[i].name));
      }
      continue;
    }
    rows.push(...fetched);
  }
  return rows;
}

function isFetchable(conn) {
  // Outputs are the operator's inbox — member-role connections are never asked (the daemon would reject them anyway).
  if (conn?.role === "member") return false;
  return conn != null && (conn.status == null || conn.status === "online");
}

// Per-connection model: rows cached and refreshed per connection, so one daemon never re-fans-out the whole inbox.
export function useAllOutputs({ connections, status, activeId = null, deferMs = OTHERS_DEFER_MS, enabled = true } = {}) {
  const list = Array.isArray(connections) ? connections : [];
  const sig = list.map((c) => `${c.id}:${c.name}:${c.status ?? ""}:${c.role ?? ""}:${_authId(c)}`).join("|");
  const statusKey = String(status ?? "");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const byConnRef = useRef(new Map());
  const seqRef = useRef(new Map());
  const inflightRef = useRef(0);
  const seenSigRef = useRef(new Map());
  const authRef = useRef(new Map());
  const timersRef = useRef(new Map());
  const queueRef = useRef([]);
  const prevStatusKeyRef = useRef(statusKey);
  const listRef = useRef(list);
  listRef.current = list;
  const statusRef = useRef(status);
  statusRef.current = status;
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  // Scheduled work counts as loading: the sync bar must not blink off between a resolved batch and the queued remainder.
  const recount = useCallback(() => {
    setLoading(
      inflightRef.current > 0 || queueRef.current.length > 0 || timersRef.current.size > 0,
    );
  }, []);

  const mergeRows = useCallback(() => {
    const ids = new Set(listRef.current.map((c) => c.id));
    const merged = [];
    for (const [id, r] of byConnRef.current) {
      if (ids.has(id)) merged.push(...r);
      else byConnRef.current.delete(id);
    }
    merged.sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0));
    setRows(merged);
  }, []);

  const refreshConn = useCallback(async (conn) => {
    if (!conn?.id) return;
    // Guard BEFORE the RPC: refresh() and event-driven paths funnel here, so a member/offline connection is never asked (the post-fetch guard below only covers going-offline mid-flight).
    if (!isFetchable(listRef.current.find((x) => x.id === conn.id) ?? conn)) return;
    const seq = (seqRef.current.get(conn.id) ?? 0) + 1;
    seqRef.current.set(conn.id, seq);
    inflightRef.current += 1;
    recount();
    try {
      const key = _memoryKey(conn.id, _authId(conn), String(statusRef.current ?? ""));
      const previous = byConnRef.current.get(conn.id) ?? _rowsMemory.get(key) ?? null;
      const fetched = await fetchConnectionOutputs(conn, statusRef.current, previous).catch(() => null);
      if (seqRef.current.get(conn.id) !== seq || !enabledRef.current) return;
      // null = the daemon was unreachable: keep the last-known rows instead of blanking them.
      if (fetched === null) return;
      // A connection that went offline mid-flight must not resurrect: commit only against its live, fetchable self.
      if (!isFetchable(listRef.current.find((x) => x.id === conn.id))) return;
      byConnRef.current.set(conn.id, fetched);
      _rowsMemory.set(key, fetched);
      mergeRows();
    } finally {
      inflightRef.current -= 1;
      recount();
      pumpRef.current?.();
    }
  }, [mergeRows, recount]);

  const pumpRef = useRef(null);
  // Explicit-open fan-out: bounded concurrency instead of time stagger — each resolution frees the next slot.
  const pump = useCallback(() => {
    while (
      enabledRef.current
      && inflightRef.current < OPEN_MAX_CONCURRENT
      && queueRef.current.length > 0
    ) {
      const id = queueRef.current.shift();
      const cur = listRef.current.find((x) => x.id === id);
      if (cur && isFetchable(cur)) refreshConn(cur);
    }
    recount();
  }, [refreshConn, recount]);
  pumpRef.current = pump;

  // refresh(id) scopes to one connection; unknown/absent id falls back to every connection.
  const refresh = useCallback(async (connectionId = null) => {
    const all = listRef.current;
    const scoped = connectionId ? all.filter((c) => c.id === connectionId) : [];
    await Promise.all((scoped.length ? scoped : all).map((c) => refreshConn(c)));
  }, [refreshConn]);

  useEffect(() => {
    if (!enabled) {
      // Disable = full stand-down: kill deferred and queued fetches, invalidate in-flight commits, forget signatures so re-enable refetches from scratch.
      for (const pending of timersRef.current.values()) clearTimeout(pending);
      timersRef.current.clear();
      queueRef.current.length = 0;
      seenSigRef.current.clear();
      for (const [id, n] of seqRef.current) seqRef.current.set(id, n + 1);
      recount();
      return;
    }
    if (prevStatusKeyRef.current !== statusKey) {
      // The filter changed: every cached row answers the old query — drop caches, invalidate in-flight commits, reschedule from scratch.
      prevStatusKeyRef.current = statusKey;
      seenSigRef.current.clear();
      byConnRef.current.clear();
      for (const [id, n] of seqRef.current) seqRef.current.set(id, n + 1);
      mergeRows();
    }
    if (list.length === 0) {
      byConnRef.current.clear();
      setRows([]);
      return;
    }
    for (const c of list) {
      const auth = _authId(c);
      const prevAuth = authRef.current.get(c.id);
      if (prevAuth !== undefined && prevAuth !== auth) {
        // Same endpoint re-paired with new credentials: the old credential's rows must never show.
        byConnRef.current.delete(c.id);
        purgeOutputsMemory(c.id);
        seqRef.current.set(c.id, (seqRef.current.get(c.id) ?? 0) + 1);
        mergeRows();
      }
      authRef.current.set(c.id, auth);
    }
    let seeded = false;
    for (const c of list) {
      if (byConnRef.current.has(c.id) || !isFetchable(c)) continue;
      const remembered = _rowsMemory.get(_memoryKey(c.id, _authId(c), statusKey));
      if (remembered) {
        byConnRef.current.set(c.id, remembered);
        seeded = true;
      }
    }
    if (seeded) mergeRows();
    let othersDelay = deferMs;
    for (const c of list) {
      const s = `${c.name}:${c.status ?? ""}:${c.role ?? ""}:${_authId(c)}`;
      if (seenSigRef.current.get(c.id) === s) continue;
      seenSigRef.current.set(c.id, s);
      const pending = timersRef.current.get(c.id);
      if (pending) {
        clearTimeout(pending);
        timersRef.current.delete(c.id);
      }
      if (c.status === "offline" || c.status === "disabled" || c.status === "auth-failed" || c.role === "member") {
        byConnRef.current.delete(c.id);
        _rowsMemory.delete(_memoryKey(c.id, _authId(c), statusKey));
        seqRef.current.set(c.id, (seqRef.current.get(c.id) ?? 0) + 1);
        queueRef.current = queueRef.current.filter((id) => id !== c.id);
        mergeRows();
        continue;
      }
      // unknown/probing never fetch — the single fetch fires on the transition to online.
      if (!isFetchable(c)) continue;
      if (activeIdRef.current != null && c.id !== activeIdRef.current) {
        if (deferMs <= 0) {
          if (!queueRef.current.includes(c.id)) queueRef.current.push(c.id);
        } else {
          const delay = othersDelay;
          othersDelay += OTHERS_STAGGER_MS;
          timersRef.current.set(c.id, setTimeout(() => {
            timersRef.current.delete(c.id);
            const cur = listRef.current.find((x) => x.id === c.id);
            if (cur) refreshConn(cur);
            else recount();
          }, delay));
        }
      } else {
        refreshConn(c);
      }
    }
    pump();
    for (const id of Array.from(seenSigRef.current.keys())) {
      if (!list.some((c) => c.id === id)) {
        seenSigRef.current.delete(id);
        authRef.current.delete(id);
        purgeOutputsMemory(id);
        const pending = timersRef.current.get(id);
        if (pending) {
          clearTimeout(pending);
          timersRef.current.delete(id);
        }
        queueRef.current = queueRef.current.filter((qid) => qid !== id);
        byConnRef.current.delete(id);
        mergeRows();
      }
    }
    recount();
  }, [sig, statusKey, enabled, deferMs, mergeRows, refreshConn, pump, recount]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => {
    for (const pending of timersRef.current.values()) clearTimeout(pending);
  }, []);

  // Refresh on any daemon's output mutation (active stream emits output.created/updated) AND on background-poll notifications (flagged, since the poller carries agent.message/etc., not output.created) — scoped to the event's connection.
  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    let refreshTimer = null;
    let pendingTarget;
    const unsub = subscribeDaemonEvent((event) => {
      if (cancelled) return;
      const payload = event.payload ?? {};
      const frame = payload.frame ?? payload;
      const isOutputEvent = frame?.event === "output.created" || frame?.event === "output.updated";
      if (!payload.background && !isOutputEvent) return;
      const target = payload.connection_id ?? activeIdRef.current ?? null;
      if (refreshTimer) {
        // Two daemons in one debounce window → widen to a full refresh.
        if (pendingTarget !== target) pendingTarget = null;
        return;
      }
      pendingTarget = target;
      refreshTimer = setTimeout(() => {
        refreshTimer = null;
        if (!cancelled) refresh(pendingTarget);
      }, 400);
    });
    return () => {
      cancelled = true;
      if (refreshTimer) clearTimeout(refreshTimer);
      unsub();
    };
  }, [refresh, enabled]);

  useEffect(() => {
    if (!enabled) return undefined;
    _localListeners.add(refresh);
    return () => { _localListeners.delete(refresh); };
  }, [refresh, enabled]);

  return { rows, loading, refresh };
}


export function useOutput(profile, id, connectionId) {
  const [row, setRow] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!profile || !id) {
      setRow(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await invoke("outputs_read", { profile, id, ...(connectionId ? { connectionId } : {}) });
      setRow(res || null);
    } catch (e) {
      setError(e);
      setRow(null);
    } finally {
      setLoading(false);
    }
  }, [profile, id, connectionId]);

  useEffect(() => { load(); }, [load]);

  const markRead = useCallback(async () => {
    if (!profile || !id) return;
    try {
      const out = await invoke("outputs_mark_read", { profile, id, ...(connectionId ? { connectionId } : {}) });
      if (out) {
        setRow(out);
        notifyLocalChange(connectionId ?? null);
      }
    } catch {
      /* best-effort */
    }
  }, [profile, id, connectionId]);

  return { row, loading, error, reload: load, markRead };
}


export function useMarkAllOutputsRead() {
  return useCallback(async (profile, connectionId) => {
    if (!profile) return 0;
    try {
      const count = await invoke("outputs_mark_all_read", { profile, ...(connectionId ? { connectionId } : {}) });
      const n = Number(count) || 0;
      if (n > 0) notifyLocalChange(connectionId ?? null);
      return n;
    } catch {
      return 0;
    }
  }, []);
}


// Keyed by connectionId:profile:id — ids are unique only within a daemon's profile, so the unified inbox must namespace by connection.
const _pendingDeletes = new Map();

function _pendingKey(connectionId, profile, id) {
  return `${connectionId}:${profile}:${id}`;
}

// Same composite key the undo timer uses — the modal hides/deletes by this so identical ids on two daemons never collide.
export function rowKey(row) {
  return _pendingKey(row?.connectionId, row?.profile, row?.id);
}

export function pendingDeleteKeys() {
  return Array.from(_pendingDeletes.keys());
}

export function useDeleteOutput() {
  const schedule = useCallback((profile, id, { delayMs = 5000, connectionId } = {}) => {
    if (!profile || !id) return;
    const key = _pendingKey(connectionId, profile, id);
    const prev = _pendingDeletes.get(key);
    if (prev) clearTimeout(prev);
    const timer = setTimeout(async () => {
      _pendingDeletes.delete(key);
      try {
        await invoke("outputs_delete", { profile, id, ...(connectionId ? { connectionId } : {}) });
        notifyLocalChange(connectionId ?? null);
      } catch {
        /* best-effort: row may already be gone */
      }
    }, delayMs);
    _pendingDeletes.set(key, timer);
  }, []);

  const cancel = useCallback((profile, id, connectionId) => {
    const key = _pendingKey(connectionId, profile, id);
    const timer = _pendingDeletes.get(key);
    if (!timer) return false;
    clearTimeout(timer);
    _pendingDeletes.delete(key);
    return true;
  }, []);

  return { schedule, cancel };
}
