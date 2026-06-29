import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { subscribeDaemonEvent } from "../lib/daemon-bus.js";

// Cache-first: a transient failure keeps the last snapshot; only auth-failed drops it.
const _cache = new Map();

function makeKey(connectionId, profile) {
  return `${connectionId || "local"}|${profile}`;
}

const _REFRESH_KINDS = new Set([
  "config_changed", "email_changed", "peers_changed", "memory_changed",
  "schedule.changed", "schedule.done", "schedule.failed",
  "workgroup_changed", "workgroup_meta", "workgroup_members",
]);

export function useProfileSnapshot(connectionId, profile) {
  const key = makeKey(connectionId, profile);
  const [snapshot, setSnapshot] = useState(() => _cache.get(key) ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    if (!profile) return Promise.resolve(null);
    setLoading(true);
    return invoke("settings_profile_snapshot", {
      profile, ...(connectionId ? { connectionId } : {}),
    })
      .then((s) => {
        if (s && typeof s === "object") { _cache.set(key, s); setSnapshot(s); }
        setError(null);
        return s;
      })
      .catch((e) => {
        const msg = String(e);
        if (msg.includes("auth-failed")) { _cache.delete(key); setSnapshot(null); }
        setError(msg);
        return null;
      })
      .finally(() => setLoading(false));
  }, [connectionId, profile, key]);

  useEffect(() => {
    if (!profile) { setSnapshot(null); return undefined; }
    setSnapshot(_cache.get(key) ?? null);
    load();
    return undefined;
  }, [key, profile, load]);

  const timerRef = useRef(null);
  useEffect(() => {
    if (!profile) return undefined;
    const unsub = subscribeDaemonEvent((event) => {
      const payload = event?.payload ?? {};
      const frame = payload.frame ?? payload;
      if (connectionId && payload.connection_id && payload.connection_id !== connectionId) return;
      const evProfile = frame?.data?.profile;
      if (evProfile && evProfile !== profile) return;
      if (!_REFRESH_KINDS.has(frame?.event)) return;
      // Coalesce a reconnect-replay burst into one refetch.
      if (timerRef.current) return;
      timerRef.current = setTimeout(() => { timerRef.current = null; load(); }, 300);
    });
    return () => {
      if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
      unsub();
    };
  }, [connectionId, profile, load]);

  return { snapshot, loading, error, refresh: load };
}

export function _clearProfileSnapshotCache() {
  _cache.clear();
}
