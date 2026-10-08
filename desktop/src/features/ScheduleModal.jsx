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

const REFRESH_EVENTS = new Set(["schedule.changed", "schedule.done", "schedule.failed"]);

function jobTitle(j) {
  return j.title?.trim() || j.prompt?.trim().split("\n")[0] || `(job · ${String(j.id).slice(0, 6)})`;
}

function jobState(j) {
  if (j.paused) return "paused";
  return j.last_run_status === "error" ? "failed" : "active";
}

function JobStatus({ job }) {
  const state = jobState(job);
  return (
    <span className={styles.status} data-state={state}>
      <span className={styles.dot} data-on={state === "active" ? "on" : state === "paused" ? "off" : "fail"} aria-hidden />
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

  const fire = (id) => mutate("run", id, () => invoke("schedule_fire", { profile, ...connArg, id }), `Fired ${jobTitle(active)}`);
  const setPaused = (id, paused) => mutate(paused ? "pause" : "resume", id, () => invoke("schedule_set_paused", { profile, ...connArg, id, paused }));
  const remove = (id) => mutate("delete", id, () => invoke("schedule_remove", { profile, ...connArg, id }));

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
            const state = jobState(j);
            const word = nextRunWord(j);
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
                    <span className={styles.dot} data-on={state === "active" ? "on" : state === "paused" ? "off" : "fail"} aria-hidden />
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
            <JobStatus job={active} />
            <span className={shell.detailMetaSpacer} />
            <span className={styles.detailId}>{active.id}</span>
          </div>
          <div className={shell.detailScroll}>
            {banner ? (
              <AlertBanner lead={banner.lead} detail={banner.detail} action="Run now" onAction={() => fire(active.id)} disabled={busy} />
            ) : null}
            <div className={styles.actions}>
              {banner ? null : <Button size="sm" variant="secondary" onClick={() => fire(active.id)} disabled={busy}>Run now</Button>}
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
            <dl className={`${styles.fields} ${active.paused ? styles.paused : ""}`}>
              {active.description ? <div><dt>about</dt><dd>{active.description}</dd></div> : null}
              <div>
                <dt>when</dt>
                <dd>{describeWhen(active)}{rawWhen(active) ? <span className={styles.chip}>{rawWhen(active)}</span> : null}</dd>
              </div>
              {!active.paused && active.next_fire ? <div><dt>next</dt><dd>{formatNextFire(active.next_fire)}</dd></div> : null}
              <div>
                <dt>last run</dt>
                <dd className={failed ? styles.failed : ""}>{formatLastRun(active.last_run_at, active.last_run_status)}</dd>
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
