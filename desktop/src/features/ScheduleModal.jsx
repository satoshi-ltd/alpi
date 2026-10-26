import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { AlertBanner, Button, ConfirmDelete, Eyebrow, IconBtn } from "../primitives/index.js";
import { I } from "../primitives/icons.jsx";
import shell from "../primitives/BrowseModal.module.css";
import { BrowseBody, BrowseShell } from "../primitives/BrowseModal.jsx";
import { PROFILE_PANELS } from "../lib/profilePanels.js";
import { SkeletonReader, SkeletonRows } from "../primitives/Skeleton.jsx";
import MarkdownBody from "../primitives/MarkdownBody.jsx";
import { subscribeDaemonEvent } from "../lib/daemon-bus.js";
import { useNotify } from "../primitives/Notification.jsx";
import { formatLastRun } from "./settings/util.js";
import { describeTimeout, describeWhen, rawWhen } from "../../../common/schedule.mjs";
import { jobBanner, jobGroups, jobItem, nextRunWord } from "../../../common/attention.mjs";
import { formatNextFire, lastRunShort } from "../lib/time.js";
import styles from "./ScheduleModal.module.css";
import { EMPTY } from "../../../common/emptyCopy.mjs";
import { statusDot } from "../lib/statusVocab.js";
import { toEpochSeconds, useActivity } from "../hooks/useActivity.js";

const REFRESH_EVENTS = new Set(["schedule.changed", "schedule.done", "schedule.failed"]);

function jobTitle(j) {
  return j.title?.trim() || j.prompt?.trim().split("\n")[0] || `(job · ${String(j.id).slice(0, 6)})`;
}

function jobState(j, running = false) {
  if (running) return "running";
  if (j.paused) return "paused";
  return j.last_run_status === "error" ? "failed" : "active";
}

function JobStatus({ job, running }) {
  const state = jobState(job, running);
  return (
    <span className={styles.status} data-state={state}>
      <span className={styles.dot} data-on={{ filled: "on", hollow: "off", red: "fail" }[statusDot(state)]} aria-hidden />
      {state}
    </span>
  );
}

function matchesJob(j, query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) return true;
  return [j.title, j.description, j.prompt, j.expression, j.id, describeWhen(j)].filter(Boolean).join(" ").toLowerCase().includes(needle);
}

export function SchedulePanel({ open = true, profile, connectionId, openJob = null, owner = null, onSection = null, attention = null }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const notify = useNotify();
  const genRef = useRef(0);
  const terminalRef = useRef(new Map());
  const { activity, refresh: refreshActivity } = useActivity({ connectionId, online: open });
  const [requested, setRequested] = useState({});
  const [now, setNow] = useState(Date.now);
  const runningRows = useMemo(() => new Map(
    (activity?.running ?? []).filter((r) => r.profile === profile && r.job_id != null)
      .map((r) => [String(r.job_id), r]),
  ), [activity, profile]);
  const startedAt = (id) => toEpochSeconds(runningRows.get(String(id))?.started_at) * 1000 || requested[id] || null;
  const isRunning = (id) => runningRows.has(String(id)) || requested[id] != null;
  const activeRunning = selectedId != null && isRunning(selectedId);
  const elapsed = selectedId == null ? 0 : Math.max(0, Math.floor((now - (startedAt(selectedId) || now)) / 1000));
  const runLabel = activeRunning ? `Running · ${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}` : "Run now";

  useEffect(() => {
    if (!open || (!runningRows.size && !Object.keys(requested).length)) return undefined;
    const tick = () => {
      const at = Date.now();
      setNow(at);
      setRequested((prev) => {
        const keep = Object.entries(prev).filter(([id, since]) => !runningRows.has(id) && at - since < 10000);
        return keep.length === Object.keys(prev).length ? prev : Object.fromEntries(keep);
      });
    };
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [open, runningRows, requested]);

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
    setRequested({});
    terminalRef.current.clear();
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
      if (frame.event === "schedule.done" || frame.event === "schedule.failed") {
        const id = String(frame.data?.job_id ?? "");
        terminalRef.current.set(id, (terminalRef.current.get(id) || 0) + 1);
        setRequested((prev) => {
          const next = { ...prev };
          delete next[frame.data?.job_id];
          return next;
        });
        refreshActivity();
      }
      load();
    });
  }, [open, profile, connectionId]);

  useEffect(() => {
    if (!jobs.length) { if (selectedId) setSelectedId(null); return; }
    if (!jobs.some((j) => j.id === selectedId)) setSelectedId(jobGroups(jobs)[0].jobs[0].id);
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
  const groups = useMemo(() => jobGroups(filtered), [filtered]);
  const active = jobs.find((j) => j.id === selectedId) || null;
  const failed = !!active && jobState(active) === "failed";
  const flagged = active ? jobItem(attention, active.id) : null;
  const okAt = flagged?.last_ok_at ?? active?.last_ok_at ?? null;
  const banner = failed ? jobBanner({ message: flagged?.message ?? active.last_run_message, last_ok_at: okAt }, lastRunShort(okAt)) : null;

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

  const fire = (id) => {
    if (isRunning(id)) return;
    const gen = genRef.current;
    const terminal = terminalRef.current.get(String(id)) || 0;
    return mutate("run", id, async () => {
      await invoke("schedule_fire", { profile, ...connArg, id });
      if (gen !== genRef.current) return;
      if ((terminalRef.current.get(String(id)) || 0) === terminal) {
        setRequested((prev) => ({ ...prev, [id]: Date.now() }));
      }
      refreshActivity();
    }, `Requested ${jobTitle(active)}`);
  };
  const setPaused = (id, paused) => mutate(paused ? "pause" : "resume", id, () => invoke("schedule_set_paused", { profile, ...connArg, id, paused }));
  const remove = (id) => {
    if (isRunning(id)) return;
    return mutate("delete", id, () => invoke("schedule_remove", { profile, ...connArg, id }));
  };

  const list = (
    <ul className={shell.list} role="listbox">
      {loading && jobs.length === 0 ? (
        <SkeletonRows as="li" />
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
      ) : groups.map((g) => (
        <Fragment key={g.id}>
          <Eyebrow as="li" className={shell.groupHeader} role="presentation">{`${g.label} · ${g.jobs.length}`}</Eyebrow>
          {g.jobs.map((j) => {
            const state = jobState(j, isRunning(j.id));
            const word = state === "running" ? "running" : nextRunWord(j);
            return (
              <li key={j.id}>
                <button
                  type="button"
                  className={`${shell.row} ${styles.jobRow} ${j.id === selectedId ? shell.rowActive : ""}`}
                  onClick={() => setSelectedId(j.id)}
                  role="option"
                  aria-selected={j.id === selectedId}
                >
                  <span className={styles.jobHead}>
                    <span className={styles.dot} data-on={{ filled: "on", hollow: "off", red: "fail" }[statusDot(state)]} aria-hidden />
                    <span className={styles.jobTitle}>{jobTitle(j)}</span>
                    {word ? <span className={`${styles.jobWhen} ${state === "failed" ? styles.failed : ""}`.trim()}>{word}</span> : null}
                  </span>
                  {j.description ? <span className={styles.jobDesc}>{j.description}</span> : null}
                </button>
              </li>
            );
          })}
        </Fragment>
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
            <JobStatus job={active} running={activeRunning} />
            <span className={shell.detailMetaSpacer} />
            <span className={styles.detailId}>{active.id}</span>
          </div>
          <div className={shell.detailScroll}>
            {banner ? (
              <AlertBanner lead={banner.lead} detail={banner.detail} action={runLabel} onAction={() => fire(active.id)} disabled={busy || activeRunning} />
            ) : null}
            <div className={styles.actions}>
              {banner ? null : <Button size="sm" variant="secondary" onClick={() => fire(active.id)} disabled={busy || activeRunning}>{runLabel}</Button>}
              <Button size="sm" variant="ghost" onClick={() => setPaused(active.id, !active.paused)} disabled={busy || activeRunning}>
                {active.paused ? "Resume" : "Pause"}
              </Button>
              <span className={styles.deleteWrap}>
                <IconBtn tip="Delete" className={styles.deleteBtn} onClick={() => setConfirm(true)} disabled={busy || activeRunning}>
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
            <dl className={`${styles.fields} ${active.paused ? styles.paused : ""}`}>
              {active.description ? <div><dt>about</dt><dd>{active.description}</dd></div> : null}
              <div>
                <dt>when</dt>
                <dd>{describeWhen(active)}{rawWhen(active) ? <span className={styles.chip}>{rawWhen(active)}</span> : null}</dd>
              </div>
              {!active.paused && active.next_fire ? <div><dt>next</dt><dd>{formatNextFire(active.next_fire)}</dd></div> : null}
              <div>
                <dt>last run</dt>
                <dd className={failed && !activeRunning ? styles.failed : ""}>{activeRunning ? "running now" : formatLastRun(active.last_run_at, active.last_run_status)}</dd>
              </div>
              <div>
                <dt>runs</dt>
                <dd>{[active.no_agent ? "shell script" : "agent", describeTimeout(active)].filter(Boolean).join(" · ")}</dd>
              </div>
              {active.timeout_error ? (
                <div><dt>timeout</dt><dd className={styles.failed}>{active.timeout_error}</dd></div>
              ) : null}
              <div><dt>notify</dt><dd>{active.notify ? "pushes to your apps" : "silent — failures still alert"}</dd></div>
            </dl>
            <div className={styles.promptBox}>
              <div className={styles.promptRail}>
                <Eyebrow className={styles.promptLabel}>prompt</Eyebrow>
                <div className={styles.promptItem}>Prompt</div>
              </div>
              <div className={styles.promptBody}>
                {active.prompt
                  ? <MarkdownBody source={active.no_agent ? `\`\`\`sh\n${active.prompt}\n\`\`\`` : active.prompt} />
                  : <em className={styles.emptyNote}>(empty)</em>}
              </div>
            </div>
          </div>
        </>
      ) : loading ? (
        <SkeletonReader />
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
