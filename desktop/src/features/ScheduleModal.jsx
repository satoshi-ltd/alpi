import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Button, ConfirmDelete, IconBtn } from "../primitives/index.js";
import { I } from "../primitives/icons.jsx";
import shell from "../primitives/BrowseModal.module.css";
import { BrowseBody, BrowseShell } from "../primitives/BrowseModal.jsx";
import { PROFILE_PANELS } from "../lib/profilePanels.js";
import MarkdownBody from "../primitives/MarkdownBody.jsx";
import { subscribeDaemonEvent } from "../lib/daemon-bus.js";
import { useNotify } from "../primitives/Notification.jsx";
import { formatLastRun } from "./settings/util.js";
import { describeTimeout, describeWhen, rawWhen } from "../../../common/schedule.mjs";
import { formatNextFire, lastRunShort } from "../lib/time.js";
import styles from "./ScheduleModal.module.css";
import { EMPTY } from "../../../common/emptyCopy.mjs";

const REFRESH_EVENTS = new Set(["schedule.changed", "schedule.done", "schedule.failed"]);

function jobTitle(j) {
  return j.title?.trim() || j.prompt?.trim().split("\n")[0] || `(job · ${String(j.id).slice(0, 6)})`;
}

function jobFailed(j) {
  return j.last_run_status === "error" && !!j.last_run_at;
}

function JobStatus({ job }) {
  return (
    <span className={styles.status} data-state={job.paused ? "paused" : "active"}>
      <span className={styles.dot} data-on={job.paused ? "off" : "on"} aria-hidden />
      {job.paused ? "paused" : "active"}
    </span>
  );
}

function matchesJob(j, query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) return true;
  return [j.title, j.prompt, j.expression, j.id, describeWhen(j)].filter(Boolean).join(" ").toLowerCase().includes(needle);
}

export function SchedulePanel({ open = true, profile, connectionId, openJob = null, owner = null, onSection = null }) {
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
    setBusy(false);
    setSelectedId(null);
    setError(null);
    setConfirm(false);
    load();
    return () => {
      genRef.current += 1;
      setJobs([]);
    };
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

  const pendingJobRef = useRef(null);
  useEffect(() => {
    pendingJobRef.current = openJob?.id ?? null;
  }, [openJob]);
  useEffect(() => {
    const wanted = pendingJobRef.current;
    if (wanted == null) return;
    const match = jobs.find((j) => String(j.id) === String(wanted));
    if (!match) return;
    pendingJobRef.current = null;
    setSelectedId(match.id);
  }, [jobs, openJob]);

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
          <span className={shell.emptyTitle}>{EMPTY.schedule.title}</span>
          <span className={shell.emptyHint}>{EMPTY.schedule.hint}</span>
        </li>
      ) : filtered.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>{EMPTY.matches.title}</span>
          <span className={shell.emptyHint}>{EMPTY.matches.hint}</span>
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
              <span className={styles.jobCron}>{describeWhen(j)}</span>
            </span>
            {j.paused ? (
              <span className={styles.jobWhen}>paused</span>
            ) : jobFailed(j) ? (
              <span className={`${styles.jobWhen} ${styles.failed}`}>failed</span>
            ) : j.last_run_status && j.last_run_at ? (
              <span className={styles.jobWhen}>{lastRunShort(j.last_run_at)}</span>
            ) : null}
          </button>
        </li>
      ))}
    </ul>
  );

  return (
    <BrowseBody
      owner={owner}
      sections={owner ? PROFILE_PANELS : null}
      section="schedule"
      onSection={onSection}
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
            <span className={shell.detailMetaSpacer} />
            <Button size="sm" variant="secondary" onClick={() => fire(active.id)} disabled={busy}>Run now</Button>
            <Button size="sm" variant="ghost" onClick={() => setPaused(active.id, !active.paused)} disabled={busy}>
              {active.paused ? "Resume" : "Pause"}
            </Button>
            <span className={styles.deleteWrap}>
              <IconBtn tip="Delete" className={styles.deleteBtn} onClick={() => setConfirm(true)} disabled={busy}>
                <I.Trash />
              </IconBtn>
              <ConfirmDelete
                anchored={false}
                open={confirm}
                onClose={() => setConfirm(false)}
                onConfirm={() => remove(active.id)}
                title={`Delete "${jobTitle(active)}"?`}
                consequence="The job stops firing and is removed. The agent can recreate it later from chat."
              />
            </span>
          </div>
          <div className={shell.detailScroll}>
            <div className={styles.lead}>
              <JobStatus job={active} />
              <span className={styles.leadWhen}>{describeWhen(active)}</span>
              {!active.paused && active.next_fire ? <span className={styles.leadNext}>next {formatNextFire(active.next_fire)}</span> : null}
            </div>
            <dl className={`${styles.fields} ${active.paused ? styles.paused : ""}`}>
              {rawWhen(active) ? <div><dt>{active.kind}</dt><dd className="mono">{rawWhen(active)}</dd></div> : null}
              <div>
                <dt>last run</dt>
                <dd className={`mono ${jobFailed(active) ? styles.failed : ""}`.trim()}>{formatLastRun(active.last_run_at, active.last_run_status)}</dd>
              </div>
              <div>
                <dt>runs</dt>
                <dd className="mono">{[active.no_agent ? "shell script" : "agent", describeTimeout(active)].filter(Boolean).join(" · ")}</dd>
              </div>
              {active.timeout_error ? (
                <div><dt>timeout</dt><dd className={`mono ${styles.failed}`}>{active.timeout_error}</dd></div>
              ) : null}
              <div><dt>notify</dt><dd className="mono">{active.notify ? "pushes to your apps" : "silent — failures still alert"}</dd></div>
              <div><dt>id</dt><dd className="mono">{active.id}</dd></div>
            </dl>
            {active.prompt
              ? <MarkdownBody source={active.no_agent ? `\`\`\`sh\n${active.prompt}\n\`\`\`` : active.prompt} />
              : <em className={styles.emptyNote}>(empty)</em>}
          </div>
        </>
      ) : loading ? (
        <div className={shell.detailEmpty}>Loading schedule…</div>
      ) : (
        <div className={shell.detailEmpty}>Select a job.</div>
      )}
    </BrowseBody>
  );
}

export default function ScheduleModal({ open, onClose, ...panel }) {
  return (
    <BrowseShell open={open} onClose={onClose} label="Schedule">
      <SchedulePanel {...panel} />
    </BrowseShell>
  );
}
