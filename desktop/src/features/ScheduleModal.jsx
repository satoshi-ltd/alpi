import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { BrowseModal, ConfirmDelete, IconBtn, StatusPill } from "../primitives/index.js";
import { I } from "../primitives/icons.jsx";
import shell from "../primitives/BrowseModal.module.css";
import MarkdownBody from "../primitives/MarkdownBody.jsx";
import { subscribeDaemonEvent } from "../lib/daemon-bus.js";
import { useNotify } from "../primitives/Notification.jsx";
import { scheduleSummary, formatLastRun } from "./settings/util.js";
import { formatNextFire, lastRunShort } from "../lib/time.js";
import styles from "./ScheduleModal.module.css";

const REFRESH_EVENTS = new Set(["schedule.changed", "schedule.done", "schedule.failed"]);

function jobTitle(j) {
  return j.title?.trim() || j.prompt?.trim().split("\n")[0] || `(job · ${String(j.id).slice(0, 6)})`;
}

function whenField(j) {
  if (j.kind === "once") return { label: "once", value: j.run_at || "?" };
  if (j.kind === "inactivity") return { label: "inactivity", value: `after ${j.after_hours ?? "?"}h` };
  return { label: "cron", value: j.expression || "?" };
}

function matchesJob(j, query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) return true;
  return [j.title, j.prompt, j.expression, j.id].filter(Boolean).join(" ").toLowerCase().includes(needle);
}

export default function ScheduleModal({ open, onClose, profile, connectionId }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const notify = useNotify();
  const genRef = useRef(0);

  const connArg = connectionId ? { connectionId } : {};

  async function load() {
    const gen = genRef.current;
    setLoading(true);
    try {
      const list = await invoke("schedules", { profile, ...connArg });
      if (gen !== genRef.current) return;
      setJobs(Array.isArray(list) ? list : []);
      setError(null);
    } catch (e) {
      if (gen !== genRef.current) return;
      setError(String(e));
    } finally {
      if (gen === genRef.current) setLoading(false);
    }
  }

  useEffect(() => {
    if (!open || !profile) return undefined;
    genRef.current += 1;
    setJobs([]);
    setSelectedId(null);
    setError(null);
    setConfirm(false);
    load();
    return () => { genRef.current += 1; };
  }, [open, profile, connectionId]);

  useEffect(() => {
    if (!open || !profile) return undefined;
    return subscribeDaemonEvent((event) => {
      const payload = event?.payload ?? {};
      const frame = payload.frame ?? payload;
      if (!REFRESH_EVENTS.has(frame?.event)) return;
      if (frame?.data?.profile !== profile) return;
      if (connectionId && payload.connection_id && payload.connection_id !== connectionId) return;
      load();
    });
  }, [open, profile, connectionId]);

  useEffect(() => {
    if (!jobs.length) { if (selectedId) setSelectedId(null); return; }
    if (!jobs.some((j) => j.id === selectedId)) setSelectedId(jobs[0].id);
  }, [jobs, selectedId]);

  const filtered = useMemo(() => jobs.filter((j) => matchesJob(j, query)), [jobs, query]);
  const active = jobs.find((j) => j.id === selectedId) || null;

  async function mutate(kind, id, fn, okMsg) {
    const gen = genRef.current;
    setBusy(true);
    try {
      await fn();
      if (gen !== genRef.current) return;
      if (okMsg) notify({ message: okMsg, variant: "success", duration: 2000 });
      await load();
    } catch (e) {
      if (gen !== genRef.current) return;
      notify({ message: `${kind} failed: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      if (gen === genRef.current) setBusy(false);
    }
  }

  const fire = (id) => mutate("run", id, () => invoke("schedule_fire", { profile, ...connArg, id }), `Fired ${jobTitle(active)}`);
  const setPaused = (id, paused) => mutate(paused ? "pause" : "resume", id, () => invoke("schedule_set_paused", { profile, ...connArg, id, paused }));
  const remove = (id) => mutate("delete", id, () => invoke("schedule_remove", { profile, ...connArg, id }));

  const list = (
    <ul className={shell.list} role="listbox">
      {loading && jobs.length === 0 ? (
        <li className={shell.empty}><span className={shell.emptyTitle}>Loading schedule…</span></li>
      ) : error ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>Could not load schedule</span>
          <span className={shell.emptyHint}>{error}</span>
        </li>
      ) : jobs.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>No scheduled jobs</span>
          <span className={shell.emptyHint}>Ask the agent in chat to schedule something.</span>
        </li>
      ) : filtered.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>No matches</span>
          <span className={shell.emptyHint}>Try a different query, or clear it.</span>
        </li>
      ) : filtered.map((j) => (
        <li key={j.id}>
          <button
            type="button"
            className={`${shell.row} ${styles.jobRow} ${j.id === selectedId ? shell.rowActive : ""}`}
            onClick={() => setSelectedId(j.id)}
            role="option"
            aria-selected={j.id === selectedId}
          >
            <span className={styles.dot} data-on={j.paused ? "off" : "on"} aria-hidden />
            <span className={styles.jobMain}>
              <span className={styles.jobTitle}>{jobTitle(j)}</span>
              <span className={`mono ${styles.jobCron}`}>{scheduleSummary(j)}</span>
            </span>
            {j.last_run_status && j.last_run_at ? <span className={styles.jobWhen}>{lastRunShort(j.last_run_at)}</span> : null}
          </button>
        </li>
      ))}
    </ul>
  );

  return (
    <BrowseModal
      open={open}
      onClose={onClose}
      title="Schedule"
      count={jobs.length}
      kicker="jobs the agent runs on a schedule"
      search={{ value: query, onChange: setQuery, placeholder: "Search jobs…", label: "Search jobs" }}
      list={list}
      loading={loading}
      loadingLabel="Loading schedule"
    >
      {active ? (
        <>
          <div className={shell.detailMeta}>
            <span className={styles.detailTitle}>{jobTitle(active)}</span>
            <span className={`mono ${styles.detailId}`}>{active.id}</span>
            <StatusPill tone={active.paused ? "off" : "on"}>{active.paused ? "paused" : "active"}</StatusPill>
            <span className={shell.detailMetaSpacer} />
            <IconBtn tip="Run now" onClick={() => fire(active.id)} disabled={busy}><I.Play /></IconBtn>
            <IconBtn
              tip={active.paused ? "Resume" : "Pause"}
              onClick={() => setPaused(active.id, !active.paused)}
              disabled={busy}
            >
              {active.paused ? <I.Play /> : <I.Pause />}
            </IconBtn>
            <span className={styles.deleteWrap}>
              <IconBtn tip="Delete" className={styles.deleteBtn} onClick={() => setConfirm(true)} disabled={busy}>
                <I.Trash />
              </IconBtn>
              <ConfirmDelete
                mode="simple"
                open={confirm}
                onClose={() => setConfirm(false)}
                onConfirm={() => remove(active.id)}
                title={`Delete "${jobTitle(active)}"?`}
                consequence="The job stops firing and is removed. The agent can recreate it later from chat."
              />
            </span>
          </div>
          <div className={shell.detailScroll}>
            <dl className={`${styles.fields} ${active.paused ? styles.paused : ""}`}>
              <div><dt>{whenField(active).label}</dt><dd className="mono">{whenField(active).value}</dd></div>
              <div><dt>next</dt><dd className="mono">{active.paused ? "paused" : formatNextFire(active.next_fire)}</dd></div>
              <div><dt>last run</dt><dd className="mono">{formatLastRun(active.last_run_at, active.last_run_status)}</dd></div>
              <div><dt>runs</dt><dd className="mono">{active.no_agent ? "shell script" : "agent"}</dd></div>
              <div><dt>notify</dt><dd className="mono">{active.notify ? "on — pushes to your apps" : "silent — failures still alert"}</dd></div>
            </dl>
            <div className={styles.promptLabel}>{active.no_agent ? "command" : "prompt"}</div>
            {active.prompt
              ? <MarkdownBody source={active.no_agent ? `\`\`\`sh\n${active.prompt}\n\`\`\`` : active.prompt} mono />
              : <em className={styles.emptyNote}>(empty)</em>}
          </div>
        </>
      ) : loading ? (
        <div className={shell.detailEmpty}>Loading schedule…</div>
      ) : (
        <div className={shell.detailEmpty}>Select a job.</div>
      )}
    </BrowseModal>
  );
}
