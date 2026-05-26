import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

const DEFAULT_LIMIT = 100;

// In-process bus so a mark_read in one hook instance refreshes siblings (modal list + sidebar badge) before the daemon round-trips output.updated.
const _localListeners = new Set();
function notifyLocalChange() {
  for (const fn of _localListeners) {
    try { fn(); } catch { /* */ }
  }
}


export function useOutputs({ profiles, connectionId, status } = {}) {
  const profileNames = useMemo(
    () => (Array.isArray(profiles) ? profiles.map((p) => p.name ?? p).filter(Boolean) : []),
    [profiles],
  );
  const key = profileNames.join(",");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const reqRef = useRef(0);

  const refresh = useCallback(async () => {
    if (!profileNames.length) {
      setRows([]);
      return;
    }
    const id = ++reqRef.current;
    setLoading(true);
    try {
      const lists = await Promise.all(
        profileNames.map((name) =>
          invoke("outputs_list", {
            profile: name,
            ...(status ? { status } : {}),
            limit: DEFAULT_LIMIT,
          })
            .then((res) =>
              (Array.isArray(res) ? res : []).map((o) => ({
                ...o,
                profile: o.profile || name,
              })),
            )
            .catch(() => []),
        ),
      );
      if (id !== reqRef.current) return;
      const merged = lists
        .flat()
        .sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0));
      setRows(merged);
    } finally {
      if (id === reqRef.current) setLoading(false);
    }
  }, [key, status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    refresh();
  }, [refresh, connectionId]);

  useEffect(() => {
    let unlisten = null;
    let cancelled = false;
    listen("daemon-event", (event) => {
      if (cancelled) return;
      const payload = event.payload ?? {};
      if (payload.connection_id && connectionId && payload.connection_id !== connectionId) return;
      const frame = payload.frame ?? payload;
      if (frame?.event === "output.created" || frame?.event === "output.updated") refresh();
    })
      .then((fn) => { if (cancelled) fn?.(); else unlisten = fn; })
      .catch(() => {});
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [refresh, connectionId]);

  useEffect(() => {
    _localListeners.add(refresh);
    return () => { _localListeners.delete(refresh); };
  }, [refresh]);

  return { rows, loading, refresh };
}


export function useOutput(profile, id) {
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
      const res = await invoke("outputs_read", { profile, id });
      setRow(res || null);
    } catch (e) {
      setError(e);
      setRow(null);
    } finally {
      setLoading(false);
    }
  }, [profile, id]);

  useEffect(() => { load(); }, [load]);

  const markRead = useCallback(async () => {
    if (!profile || !id) return;
    try {
      const out = await invoke("outputs_mark_read", { profile, id });
      if (out) {
        setRow(out);
        notifyLocalChange();
      }
    } catch {
      /* best-effort */
    }
  }, [profile, id]);

  return { row, loading, error, reload: load, markRead };
}


export function useMarkAllOutputsRead() {
  return useCallback(async (profile) => {
    if (!profile) return 0;
    try {
      const count = await invoke("outputs_mark_all_read", { profile });
      const n = Number(count) || 0;
      if (n > 0) notifyLocalChange();
      return n;
    } catch {
      return 0;
    }
  }, []);
}
