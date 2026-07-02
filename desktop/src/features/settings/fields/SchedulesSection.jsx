import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { subscribeDaemonEvent } from "../../../lib/daemon-bus.js";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Section } from "../primitives.jsx";
import settingsStyles from "../Settings.module.css";
import { ScheduleRow as DsScheduleRow, ScheduleList as DsScheduleList } from "../../../primitives/SettingsLayout.jsx";
import { scheduleSummary, formatLastRun } from "../util.js";

function cacheKey(connectionId, profileName) {
  return `${connectionId || "local"}|${profileName}`;
}

const _jobsCache = new Map();

const SCHEDULE_REFRESH_EVENTS = new Set([
  "schedule.changed", "schedule.done", "schedule.failed",
]);

export function _clearScheduleCache() {
  _jobsCache.clear();
}

export function SchedulesSection({
  profile,
  connectionId = null,
  prefetched,
  onSnapshotRefresh = null,
  onLoadingChange,
}) {
  const prefetchedMode = prefetched !== undefined;
  const key = cacheKey(connectionId, profile.name);
  const [jobs, setJobs] = useState(() => (prefetchedMode ? prefetched : _jobsCache.get(key) ?? null));
  const [loadError, setLoadError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [loading, setLoading] = useState(!prefetchedMode);
  const notify = useNotify();
  const targetRef = useRef({ profile: profile.name, connectionId });
  const genRef = useRef(0);

  const connArg = connectionId ? { connectionId } : {};

  async function load({ force = false } = {}) {
    if (prefetchedMode) {
      if (!force || !onSnapshotRefresh) return;
      setLoading(true);
      try {
        await onSnapshotRefresh();
      } finally {
        setLoading(false);
      }
      return;
    }
    const gen = genRef.current;
    setLoading(true);
    try {
      const list = await invoke("schedules", { profile: profile.name, ...connArg });
      if (gen !== genRef.current) return;
      const next = Array.isArray(list) ? list : [];
      _jobsCache.set(key, next);
      setJobs(next);
      setLoadError(null);
    } catch (e) {
      if (gen !== genRef.current) return;
      setJobs(_jobsCache.get(key) ?? []);
      setLoadError(String(e));
    } finally {
      if (gen === genRef.current) setLoading(false);
    }
  }

  useEffect(() => {
    genRef.current += 1;
    targetRef.current = { profile: profile.name, connectionId };
    if (prefetchedMode) {
      setJobs(prefetched);
      _jobsCache.set(key, Array.isArray(prefetched) ? prefetched : []);
      setLoadError(null);
      setBusyId(null);
      setLoading(false);
      return;
    }
    setJobs(_jobsCache.get(key) ?? null);
    setLoadError(null);
    setBusyId(null);
    load();
  }, [profile.name, connectionId, key, prefetchedMode, prefetched]);

  useEffect(() => {
    onLoadingChange?.(loading);
  }, [loading, onLoadingChange]);

  useEffect(() => {
    if (prefetchedMode) return undefined;
    return subscribeDaemonEvent((event) => {
      const payload = event?.payload ?? {};
      const frame = payload.frame ?? payload;
      if (!SCHEDULE_REFRESH_EVENTS.has(frame?.event)) return;
      if (frame?.data?.profile !== profile.name) return;
      if (connectionId && payload.connection_id && payload.connection_id !== connectionId) return;
      load();
    });
  }, [profile.name, connectionId, prefetchedMode]);

  function pinnedTarget() {
    return {
      profile: targetRef.current.profile,
      ...(targetRef.current.connectionId ? { connectionId: targetRef.current.connectionId } : {}),
    };
  }

  async function fire(id) {
    const gen = genRef.current;
    const target = pinnedTarget();
    setBusyId(`fire:${id}`);
    try {
      await invoke("schedule_fire", { ...target, id });
      if (gen !== genRef.current) return;
      notify({ message: `Schedule ${id} started`, variant: "success", duration: 2000 });
      await load({ force: true });
    } catch (e) {
      if (gen !== genRef.current) return;
      notify({ message: `fire failed: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      if (gen === genRef.current) setBusyId(null);
    }
  }

  async function setPaused(id, paused) {
    const gen = genRef.current;
    const target = pinnedTarget();
    setBusyId(`pause:${id}`);
    try {
      await invoke("schedule_set_paused", { ...target, id, paused });
      if (gen !== genRef.current) return;
      await load({ force: true });
    } catch (e) {
      if (gen !== genRef.current) return;
      notify({
        message: `${paused ? "pause" : "resume"} failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      if (gen === genRef.current) setBusyId(null);
    }
  }

  async function remove(id) {
    const gen = genRef.current;
    const target = pinnedTarget();
    setBusyId(`del:${id}`);
    try {
      await invoke("schedule_remove", { ...target, id });
      if (gen !== genRef.current) return;
      await load({ force: true });
    } catch (e) {
      if (gen !== genRef.current) return;
      notify({ message: `delete failed: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      if (gen === genRef.current) setBusyId(null);
    }
  }

  if (loadError) {
    return (
      <Section title="Schedule" tooltip="recurring agent tasks">
        <div role="alert" className={settingsStyles.error}>
          Could not load schedule: {loadError}
        </div>
      </Section>
    );
  }
  if (jobs === null) {
    return (
      <Section title="Schedule" tooltip="recurring agent tasks">
        <span className={settingsStyles.muted}>loading…</span>
      </Section>
    );
  }
  if (jobs.length === 0) return null;
  return (
    <Section title="Schedule" tooltip="recurring agent tasks">
      <DsScheduleList>
        {jobs.map((j) => (
          <DsScheduleRow
            key={j.id}
            s={{
              id: j.id,
              cron: scheduleSummary(j),
              title: j.title || "",
              prompt: j.prompt || "",
              on: !j.paused,
              lastRun: formatLastRun(j.last_run_at, j.last_run_status),
            }}
            onFire={() => fire(j.id)}
            onToggle={() => setPaused(j.id, !j.paused)}
            onDelete={() => remove(j.id)}
          />
        ))}
      </DsScheduleList>
    </Section>
  );
}
