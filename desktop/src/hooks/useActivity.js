import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { subscribeDaemonEvent } from "../lib/daemon-bus.js";
import { classifyDaemonPayload } from "../lib/daemon-frame.js";

export const ACTIVITY_DEBOUNCE_MS = 300;
const FAILED_WINDOW_S = 24 * 60 * 60;
const EMPTY = { needs_you: [], running: [], scheduled: [] };

export function isMissingVerb(err) {
  const text = String(err?.message ?? err ?? "").toLowerCase();
  return /-32601\b/.test(text) || /method[-_ ]not[-_ ]found/.test(text) || text.includes("unknown method");
}

export function normalizeActivity(raw) {
  if (!raw || typeof raw !== "object") return EMPTY;
  const list = (v) => (Array.isArray(v) ? v.filter((x) => x && typeof x === "object") : []);
  return {
    needs_you: list(raw.needs_you),
    running: list(raw.running),
    scheduled: list(raw.scheduled),
  };
}

export function toEpochSeconds(value) {
  if (value == null || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? (value > 1e12 ? value / 1000 : value) : null;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms / 1000;
}

export function recentlyFailed(job, nowS = Date.now() / 1000) {
  if (job?.last_run_status !== "error") return false;
  const at = toEpochSeconds(job.last_run_at);
  return at != null && nowS - at <= FAILED_WINDOW_S;
}

export const workgroupKey = (profile, id) => `${profile}/${id}`;

export function rosterStates(activity, { pendingProfiles = null, nowS = Date.now() / 1000 } = {}) {
  const profiles = {};
  const workgroups = {};
  const rank = { "needs-you": 3, failed: 2, working: 1 };
  const bump = (name, state) => {
    if (!name) return;
    if ((rank[state] ?? 0) > (rank[profiles[name]] ?? 0)) profiles[name] = state;
  };
  const a = activity ?? EMPTY;
  for (const item of a.needs_you) bump(item.profile, "needs-you");
  for (const job of a.scheduled) if (recentlyFailed(job, nowS)) bump(job.profile, "failed");
  for (const run of a.running) {
    if (run.kind === "workgroup") {
      if (!run.profile || !run.workgroup_id) continue;
      workgroups[workgroupKey(run.profile, run.workgroup_id)] = {
        state: "working",
        phasesDone: Number.isInteger(run.phases_done) ? run.phases_done : null,
        phasesTotal: Number.isInteger(run.phases_total) ? run.phases_total : null,
        phase: run.phase ?? null,
      };
    } else {
      bump(run.profile, "working");
    }
  }
  if (pendingProfiles) for (const name of pendingProfiles) bump(name, "working");
  return { profiles, workgroups };
}

export function useActivity({ connectionId, online = true }) {
  const [activity, setActivity] = useState(null);
  const [supported, setSupported] = useState(true);
  const connRef = useRef(connectionId);
  const timerRef = useRef(null);
  const seqRef = useRef(0);

  const fetchNow = useCallback(() => {
    const conn = connRef.current;
    const seq = ++seqRef.current;
    return invoke("activity_list", { connectionId: conn ?? null })
      .then((res) => {
        if (seq !== seqRef.current || connRef.current !== conn) return;
        setSupported(true);
        setActivity(normalizeActivity(res));
      })
      .catch((err) => {
        if (seq !== seqRef.current || connRef.current !== conn) return;
        if (isMissingVerb(err)) {
          setSupported(false);
          setActivity(null);
        }
      });
  }, []);

  const schedule = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      fetchNow();
    }, ACTIVITY_DEBOUNCE_MS);
  }, [fetchNow]);

  useEffect(() => {
    connRef.current = connectionId;
    setActivity(null);
    setSupported(true);
    if (online) fetchNow();
  }, [connectionId, online, fetchNow]);

  useEffect(() => {
    const unsub = subscribeDaemonEvent((e) => {
      const payload = e?.payload ?? {};
      const cls = classifyDaemonPayload(payload, connRef.current);
      if (cls === "drop") return;
      const frame = payload.frame ?? payload;
      if (cls === "replay" || frame?.event === "activity.changed") schedule();
    });
    return () => {
      unsub();
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = null;
    };
  }, [schedule]);

  const counts = useMemo(() => ({
    needsYou: activity?.needs_you.length ?? 0,
    running: activity?.running.length ?? 0,
  }), [activity]);

  return { activity, supported, counts, refresh: fetchNow };
}
