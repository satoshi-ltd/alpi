import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { subscribeDaemonEvent } from "../../../lib/daemon-bus.js";
import { ActionLink } from "../../../primitives/index.js";
import { Section, Row } from "../primitives.jsx";
import settingsStyles from "../Settings.module.css";

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
  onLoadingChange,
  onOpen,
  defer = false,
}) {
  const prefetchedMode = prefetched !== undefined;
  const key = cacheKey(connectionId, profile.name);
  const [jobs, setJobs] = useState(() => (prefetchedMode ? prefetched : _jobsCache.get(key) ?? null));
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(!prefetchedMode);
  const genRef = useRef(0);

  const connArg = connectionId ? { connectionId } : {};

  async function load() {
    if (prefetchedMode) return;
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
    if (prefetchedMode) {
      setJobs(prefetched);
      _jobsCache.set(key, Array.isArray(prefetched) ? prefetched : []);
      setLoadError(null);
      setLoading(false);
      return;
    }
    setJobs(_jobsCache.get(key) ?? null);
    setLoadError(null);
    if (defer) {
      setLoading(true);
      return;
    }
    load();
  }, [profile.name, connectionId, key, prefetchedMode, prefetched, defer]);

  useEffect(() => {
    onLoadingChange?.(loading);
  }, [loading, onLoadingChange]);

  useEffect(() => {
    if (prefetchedMode || defer) return undefined;
    return subscribeDaemonEvent((event) => {
      const payload = event?.payload ?? {};
      const frame = payload.frame ?? payload;
      if (!SCHEDULE_REFRESH_EVENTS.has(frame?.event)) return;
      if (frame?.data?.profile !== profile.name) return;
      if (connectionId && payload.connection_id && payload.connection_id !== connectionId) return;
      load();
    });
  }, [profile.name, connectionId, prefetchedMode, defer]);

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
  const active = jobs.filter((j) => !j.paused).length;
  return (
    <Section title="Schedule" tooltip="recurring agent tasks">
      <Row label="Jobs">
        <ActionLink onClick={() => onOpen?.()}>
          {jobs.length} job{jobs.length === 1 ? "" : "s"} · {active} active
        </ActionLink>
      </Row>
    </Section>
  );
}
