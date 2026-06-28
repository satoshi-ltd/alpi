import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { subscribeDaemonEvent } from "../lib/daemon-bus.js";

const DEFAULT_LIMIT = 100;

// In-process bus so a mark_read in one hook instance refreshes siblings (modal list + sidebar badge) before the daemon round-trips output.updated.
const _localListeners = new Set();
function notifyLocalChange() {
  for (const fn of _localListeners) {
    try { fn(); } catch { /* */ }
  }
}


export async function fetchConnectionOutputs(connection, status) {
  const connectionId = connection?.id;
  if (!connectionId) return [];
  let profiles;
  try {
    const res = await invoke("profile_summaries", { connectionId });
    profiles = (Array.isArray(res) ? res : []).map((p) => ({ name: p.name, accent: p.accent || null, voice_id: p.voice_id ?? null }));
  } catch {
    return [];
  }
  if (profiles.length === 0) profiles = [{ name: "default", accent: null }];
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
        .catch(() => []),
    ),
  );
  return lists.flat();
}

export function useAllOutputs({ connections, status } = {}) {
  const list = Array.isArray(connections) ? connections : [];
  // Include name+status so a rename or an online/offline flip re-fans-out (re-tagging rows, dropping an offline daemon's stale rows).
  const sig = list.map((c) => `${c.id}:${c.name}:${c.status ?? ""}`).join("|");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const reqRef = useRef(0);

  const refresh = useCallback(async () => {
    if (list.length === 0) {
      setRows([]);
      return;
    }
    const id = ++reqRef.current;
    setLoading(true);
    try {
      const perConn = await Promise.all(
        list.map((c) => fetchConnectionOutputs(c, status).catch(() => [])),
      );
      if (id !== reqRef.current) return;
      const merged = perConn
        .flat()
        .sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0));
      setRows(merged);
    } finally {
      if (id === reqRef.current) setLoading(false);
    }
  }, [sig, status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Refresh on any daemon's output mutation (active stream emits output.created/updated) AND on background-poll notifications (flagged, since the poller carries agent.message/etc., not output.created).
  useEffect(() => {
    let cancelled = false;
    let refreshTimer = null;
    const unsub = subscribeDaemonEvent((event) => {
      if (cancelled) return;
      const payload = event.payload ?? {};
      const frame = payload.frame ?? payload;
      const isOutputEvent = frame?.event === "output.created" || frame?.event === "output.updated";
      if (!payload.background && !isOutputEvent) return;
      if (refreshTimer) return;
      refreshTimer = setTimeout(() => {
        refreshTimer = null;
        if (!cancelled) refresh();
      }, 400);
    });
    return () => {
      cancelled = true;
      if (refreshTimer) clearTimeout(refreshTimer);
      unsub();
    };
  }, [refresh]);

  useEffect(() => {
    _localListeners.add(refresh);
    return () => { _localListeners.delete(refresh); };
  }, [refresh]);

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
        notifyLocalChange();
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
      if (n > 0) notifyLocalChange();
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
        notifyLocalChange();
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
