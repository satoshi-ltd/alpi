import { useEffect, useMemo, useRef, useState } from "react";
import { findLatestTask } from "../lib/workgroup-tasks.js";
import {
  loadCachedMessages,
  saveCachedMessages,
} from "../lib/workgroup-cache.js";
import { fetchWorkgroupTranscript } from "../lib/workgroup-fetch.js";
import {
  loadTaskCache,
  saveTaskCache,
} from "../lib/workgroup-task-cache.js";

const ACTIVITY_TTL_MS = 10000;
const ACTIVITY_SWEEP_MS = 3000;
const REFRESH_INITIAL_DELAY_MS = 200;
const REFRESH_BETWEEN_MS = 250;

export function useWorkgroupTasks({ workgroups, hubPubkeyOf, connectionId }) {
  // Reload + remount the per-connection caches when connectionId changes — keys (profile/wgId) collide across daemons.
  const persistedCache = useMemo(() => loadTaskCache(connectionId), [connectionId]);
  const [taskByWorkgroup, setTaskByWorkgroup] = useState(() => persistedCache.tasks);
  const seenMtimesRef = useRef(persistedCache.mtimes);
  const [activityByWorkgroup, setActivityByWorkgroup] = useState({});

  useEffect(() => {
    setTaskByWorkgroup(persistedCache.tasks);
    seenMtimesRef.current = persistedCache.mtimes;
  }, [persistedCache]);

  // Backfill cached tasks for workgroups we haven't seen yet this session.
  useEffect(() => {
    if (workgroups.length === 0) return;
    setTaskByWorkgroup((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const w of workgroups) {
        const key = `${w.profile}/${w.id}`;
        if (next[key]) continue;
        const cached = loadCachedMessages(connectionId, w.profile, w.id);
        if (cached.length === 0) continue;
        const hubName = w.hub_id ?? w.profile;
        const task = findLatestTask(cached, hubPubkeyOf(hubName));
        if (task == null) continue;
        next[key] = task;
        changed = true;
      }
      return changed ? next : prev;
    });
  }, [workgroups, hubPubkeyOf, connectionId]);

  // Refresh changed workgroups sequentially to avoid IPC saturation.
  const hubPubkeyOfRef = useRef(hubPubkeyOf);
  useEffect(() => {
    hubPubkeyOfRef.current = hubPubkeyOf;
  }, [hubPubkeyOf]);

  useEffect(() => {
    if (workgroups.length === 0) return;
    let cancelled = false;
    const seen = seenMtimesRef.current;
    const queue = workgroups.filter((w) => {
      const key = `${w.profile}/${w.id}`;
      const last = seen[key] ?? 0;
      const cur = w.mtime ?? 0;
      return cur > last;
    });
    if (queue.length === 0) return;
    async function drain() {
      await new Promise((r) => setTimeout(r, REFRESH_INITIAL_DELAY_MS));
      for (const w of queue) {
        if (cancelled) return;
        const key = `${w.profile}/${w.id}`;
        const hubName = w.hub_id ?? w.profile;
        try {
          const msgs = await fetchWorkgroupTranscript(connectionId, w.profile, w.id);
          if (cancelled) return;
          if (!Array.isArray(msgs)) continue;
          const hub = hubPubkeyOfRef.current(hubName);
          const task = findLatestTask(msgs, hub);
          setTaskByWorkgroup((prev) =>
            prev[key] === task ? prev : { ...prev, [key]: task },
          );
          seenMtimesRef.current = {
            ...seenMtimesRef.current,
            [key]: w.mtime ?? 0,
          };
          saveCachedMessages(connectionId, w.profile, w.id, msgs);
        } catch {}
        await new Promise((r) => setTimeout(r, REFRESH_BETWEEN_MS));
      }
    }
    drain();
    return () => {
      cancelled = true;
    };
  }, [workgroups, connectionId]);

  useEffect(() => {
    saveTaskCache(connectionId, { tasks: taskByWorkgroup, mtimes: seenMtimesRef.current });
  }, [taskByWorkgroup, connectionId]);

  useEffect(() => {
    const id = setInterval(() => {
      const cutoff = Date.now() - ACTIVITY_TTL_MS;
      setActivityByWorkgroup((prev) => {
        let stale = false;
        for (const ts of Object.values(prev)) {
          if (ts < cutoff) {
            stale = true;
            break;
          }
        }
        if (!stale) return prev;
        const next = {};
        for (const [k, ts] of Object.entries(prev)) {
          if (ts >= cutoff) next[k] = ts;
        }
        return next;
      });
    }, ACTIVITY_SWEEP_MS);
    return () => clearInterval(id);
  }, []);

  return {
    taskByWorkgroup,
    setTaskByWorkgroup,
    activityByWorkgroup,
    setActivityByWorkgroup,
    seenMtimesRef,
  };
}
