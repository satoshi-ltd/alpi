import { useEffect, useRef, useState } from 'react';

import { toEpochSeconds, useActivity } from '../../hooks/useActivity';

const SAFETY_MARGIN_S = 30;
const GRACE_MS = 10_000;
const GONE_MS = 2000;
const DEFAULT_TIMEOUT_S = 900;

export function elapsedLabel(seconds) {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export function useRunningJob(profile, job) {
  const { activity, supported } = useActivity();
  const [firedAt, setFiredAt] = useState(null);
  const [now, setNow] = useState(() => Date.now());
  const jobId = job?.id == null ? null : String(job.id);
  const row = jobId == null ? null : (activity?.running ?? []).find((run) => run.profile === profile && String(run.job_id) === jobId) ?? null;
  const running = !!row || firedAt !== null;
  const startedSec = row ? toEpochSeconds(row.started_at) : null;
  const startedMs = startedSec !== null ? startedSec * 1000 : firedAt;
  const ticking = useRef(false);
  ticking.current = running;
  const seen = useRef(false);
  if (row) seen.current = true;
  if (firedAt === null && !row) seen.current = false;

  useEffect(() => {
    if (!running) return undefined;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running]);

  useEffect(() => {
    if (firedAt === null || !seen.current || row) return undefined;
    const timer = setTimeout(() => setFiredAt(null), GONE_MS);
    return () => clearTimeout(timer);
  }, [firedAt, row]);

  useEffect(() => {
    if (firedAt === null || !supported || row) return undefined;
    const timer = setTimeout(() => setFiredAt(null), GRACE_MS);
    return () => clearTimeout(timer);
  }, [firedAt, supported, row]);

  useEffect(() => {
    if (firedAt === null) return undefined;
    const limit = ((Number(job?.run_timeout) || DEFAULT_TIMEOUT_S) + SAFETY_MARGIN_S) * 1000;
    const timer = setTimeout(() => setFiredAt(null), limit);
    return () => clearTimeout(timer);
  }, [firedAt, job?.run_timeout]);

  return {
    running,
    startedMs: running ? startedMs : null,
    elapsed: running && startedMs ? elapsedLabel((now - startedMs) / 1000) : null,
    started: () => setFiredAt(Date.now()),
    finished: () => setFiredAt(null),
    wasRunning: () => ticking.current,
  };
}
