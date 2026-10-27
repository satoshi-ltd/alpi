import { useEffect, useMemo, useRef, useState } from "react";
import { WORKGROUP_FOLD } from "../../../common/folds.mjs";
import { ACTIVITY_FILTERS, applyFilter, capDays, failingJobs, groupActivity, groupByDay, nextRun, stripProfilePrefix, visibleFilters } from "../../../common/activityGroups.mjs";
import { Scrim, PanelShell } from "../primitives/Panels.jsx";
import { Button, Fold, Icon, IconBtn, Kbd } from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import { useNow } from "../hooks/useNow.js";
import { isMissingVerb, toEpochSeconds } from "../hooks/useActivity.js";
import { profileLabel } from "../lib/profile-display.js";
import { clockOf, formatDay, formatNextFire, relativeTime } from "../lib/time.js";
import styles from "./ActivityPanel.module.css";
import { ICON_ROLES } from "../../../common/iconRoles.mjs";
import { EMPTY } from "../../../common/emptyCopy.mjs";
import { pluralize } from "../../../common/pluralize.mjs";

const FILTER_LABEL = { all: "All", needs: "Needs you", failing: "Failing", running: "Running", upcoming: "Upcoming" };
const FILTER_EMPTY = {
  needs: "Nothing needs you",
  failing: "No failing jobs",
  running: "Nothing running",
  upcoming: "Nothing upcoming",
};

function ago(seconds, now) {
  if (!seconds) return "";
  const rel = relativeTime(seconds, now);
  return rel === "now" ? "just now" : `${rel} ago`;
}

function Row({ glyph = null, title, sub = null, lead = null, leadTone = null, nested = false, reveal = false, action = null, onClick = null, tone = null, color = null }) {
  const body = (
    <>
      {glyph ? <span className={styles.glyph} data-tone={tone || undefined} style={color ? { "--c": color } : undefined}>{glyph}</span> : null}
      <span className={styles.text}>
        <span className={styles.title} title={title}>{title}</span>
        {sub || lead ? (
          <span className={styles.sub}>
            {lead ? <span className={styles.lead} data-tone={leadTone || undefined}>{lead}</span> : null}
            {lead && sub ? " · " : null}
            {sub}
          </span>
        ) : null}
      </span>
    </>
  );
  return (
    <li className={styles.row} data-nested={nested || undefined} data-reveal={reveal || undefined}>
      {onClick ? (
        <button type="button" className={styles.rowMain} onClick={onClick}>{body}</button>
      ) : (
        <span className={styles.rowMain}>{body}</span>
      )}
      {action ? <span className={styles.actions}>{action}</span> : null}
    </li>
  );
}

function TimedRow({ job, glyph, onClick }) {
  return (
    <li className={styles.timedRow}>
      <button type="button" className={styles.timedMain} onClick={onClick}>
        <span className={styles.time}>{clockOf(job.nextAt)}</span>
        <span className={styles.timedTitle} title={job.title || job.job_id}>{job.title || job.job_id}</span>
        <span className={styles.tag}>
          <span className={styles.glyph}>{glyph}</span>
          <span className={styles.tagName}>{profileLabel(job.profile ?? "")}</span>
        </span>
      </button>
    </li>
  );
}

function Section({ label, count, right = null, children }) {
  return (
    <section className={styles.group} aria-label={label}>
      <div className={styles.sectionHead}>
        <h3 className={`eyebrow ${styles.groupLabel}`}>{`${label} · ${count}`}</h3>
        {right}
      </div>
      <ul className={styles.list}>{children}</ul>
    </section>
  );
}

function Filters({ filter, onChange, counts, ids }) {
  const refs = useRef([]);
  const move = (event, index) => {
    const last = ids.length - 1;
    const next = { ArrowRight: index === last ? 0 : index + 1, ArrowDown: index === last ? 0 : index + 1, ArrowLeft: index === 0 ? last : index - 1, ArrowUp: index === 0 ? last : index - 1, Home: 0, End: last }[event.key];
    if (next == null) return;
    event.preventDefault();
    event.stopPropagation();
    onChange(ids[next]);
    refs.current[next]?.focus();
  };
  return (
    <div role="radiogroup" aria-label="Filter activity" className={styles.filters}>
      {ids.map((id, i) => (
        <button
          key={id}
          ref={(node) => { refs.current[i] = node; }}
          type="button"
          role="radio"
          aria-checked={filter === id}
          tabIndex={filter === id ? 0 : -1}
          className={styles.filter}
          data-on={filter === id || undefined}
          onClick={() => onChange(id)}
          onKeyDown={(e) => move(e, i)}
        >
          {FILTER_LABEL[id]}
          <span className={styles.filterCount} data-tone={id === "failing" && counts[id] > 0 ? "danger" : undefined}>{counts[id]}</span>
        </button>
      ))}
    </div>
  );
}

export default function ActivityPanel({
  open,
  onClose,
  activity,
  connectionId = null,
  accentByProfile = {},
  foldByProfile = {},
  canRetry = false,
  onRetry = null,
  onReview,
  onOpenSession,
  onOpenWorkgroup,
  onOpenProfile,
  onOpenJob,
}) {
  const now = useNow();
  const notify = useNotify();
  const [filter, setFilter] = useState("all");
  const [toggled, setToggled] = useState({});
  const [busy, setBusy] = useState(() => new Set());
  const [retryGone, setRetryGone] = useState(false);
  const [confirmAll, setConfirmAll] = useState(false);
  const [showAllUpcoming, setShowAllUpcoming] = useState(false);

  useEffect(() => {
    setRetryGone(false);
    setConfirmAll(false);
    setShowAllUpcoming(false);
  }, [connectionId]);

  useEffect(() => {
    if (!open) {
      setFilter("all");
      setToggled({});
      setConfirmAll(false);
      setShowAllUpcoming(false);
    }
  }, [open]);

  const groups = useMemo(() => groupActivity(activity, { nowMs: now }), [activity, now]);
  if (!open) return null;

  const shown = applyFilter(groups, filter);
  const retryable = Boolean(canRetry && onRetry && !retryGone);
  const total = groups.counts.all;
  const close = (fn) => (...args) => {
    fn?.(...args);
    onClose?.();
  };
  const openJob = (profile, jobId) => (onOpenJob ? onOpenJob(profile, jobId) : onOpenProfile?.(profile));
  const jobKey = (job) => `${job.profile}/${job.job_id}`;

  async function fire(job) {
    try {
      await onRetry(job.profile, job.job_id);
      return true;
    } catch (e) {
      if (isMissingVerb(e)) setRetryGone(true);
      else notify({ message: `Retry failed: ${String(e)}`, variant: "error", duration: 4000 });
      return false;
    }
  }

  async function retry(job) {
    const key = jobKey(job);
    if (busy.has(key)) return;
    setBusy((prev) => new Set(prev).add(key));
    const ok = await fire(job);
    setBusy((prev) => {
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
    if (ok) notify({ message: `Retrying ${job.title || job.job_id}`, variant: "success", duration: 2000 });
  }

  async function retryAll() {
    setConfirmAll(false);
    const jobs = failingJobs(shown);
    const keys = jobs.map(jobKey);
    setBusy((prev) => new Set([...prev, ...keys]));
    let done = 0;
    for (const job of jobs) {
      if (!(await fire(job))) break;
      done += 1;
    }
    setBusy((prev) => {
      const next = new Set(prev);
      for (const key of keys) next.delete(key);
      return next;
    });
    if (done) notify({ message: `Retrying ${done} ${pluralize(done, "job")}`, variant: "success", duration: 2000 });
  }

  const failingTotal = shown.failing.reduce((n, g) => n + g.count, 0);
  const retryAllControl = retryable && failingTotal > 0 ? (
    confirmAll ? (
      <span className={styles.confirm}>
        <span className={styles.confirmText}>Retry {failingTotal} {pluralize(failingTotal, "job")}?</span>
        <Button size="sm" variant="primary" onClick={retryAll}>Retry</Button>
        <Button size="sm" onClick={() => setConfirmAll(false)}>Cancel</Button>
      </span>
    ) : (
      <Button size="sm" onClick={() => setConfirmAll(true)}>Retry all</Button>
    )
  ) : null;

  const nothingNeeds = groups.counts.needs === 0 && groups.counts.failing === 0;
  const next = nextRun(groups);
  const filterIds = visibleFilters(groups.counts, filter);
  const upcomingDays = groupByDay(shown.upcoming, { nowMs: now });
  const capped = showAllUpcoming ? { days: upcomingDays.map((day) => ({ ...day, total: day.rows.length })), hidden: 0 } : capDays(upcomingDays);

  return (
    <Scrim onClose={onClose} top={80}>
      <PanelShell width={500} maxHeight="70vh" label="Activity">
        <div className={styles.head}>
          <Icon name={ICON_ROLES.activity} />
          <h2 className={styles.headTitle}>Activity</h2>
          <span className={styles.headKeys} aria-hidden>
            <Kbd>⌘</Kbd>
            <Kbd>J</Kbd>
          </span>
          <IconBtn tip="Close" tipSide="l" onClick={onClose}>
            <Icon name="x" />
          </IconBtn>
        </div>
        {total > 0 && filterIds.length > 0 ? <Filters filter={filter} onChange={setFilter} counts={groups.counts} ids={filterIds} /> : null}
        <div className={`scroll ${styles.body}`}>
          {total === 0 ? (
            <p className={styles.empty}>{EMPTY.activity.title}. {EMPTY.activity.hint}</p>
          ) : filter !== "all" && groups.counts[filter] === 0 ? (
            <p className={styles.empty}>{FILTER_EMPTY[filter]}</p>
          ) : null}
          {filter === "all" && total > 0 && nothingNeeds ? <p className={styles.calm}>{next ? `Nothing needs you · next ${next.title || next.job_id}, ${formatNextFire(new Date(next.nextAt * 1000).toISOString(), now)}` : "Nothing needs you now"}</p> : null}
          {shown.needs.length > 0 && (
            <Section label="Needs you" count={shown.needs.length}>
              {shown.needs.map((item) => (
                <Row
                  key={item.request_id}
                  tone="warning"
                  glyph={<Fold fold={foldByProfile[item.profile]} color={accentByProfile[item.profile] || undefined} />}
                  title={item.title || (item.kind === "clarification" ? "has a question" : "wants to run a command")}
                  sub={`${profileLabel(item.profile ?? "")} · ${item.kind === "clarification" ? "question" : "approval"} · ${ago(toEpochSeconds(item.ts), now)}`}
                  action={
                    <Button size="sm" variant="primary" onClick={close(() => onReview?.(item))}>
                      Review
                    </Button>
                  }
                />
              ))}
            </Section>
          )}
          {shown.failing.length > 0 && (
            <Section label="Failing" count={failingTotal} right={retryAllControl}>
              {shown.failing.map((group, index) => {
                const expanded = toggled[group.profile] ?? index === 0;
                const panelId = `activity-group-${group.profile}`;
                const name = profileLabel(group.profile ?? "");
                return (
                  <li key={group.profile} className={styles.failGroup}>
                    <button
                      type="button"
                      className={styles.groupHead}
                      aria-expanded={expanded}
                      aria-controls={panelId}
                      onClick={() => setToggled((prev) => ({ ...prev, [group.profile]: !expanded }))}
                    >
                      <span className={styles.chev}><Icon name={expanded ? "chev-down" : "chev-right"} size="sm" /></span>
                      <span className={styles.glyph}>
                        <Fold fold={foldByProfile[group.profile]} color={accentByProfile[group.profile] || undefined} />
                      </span>
                      <span className={styles.groupName}>{name}</span>
                      <span className={styles.groupCount}>{group.count} {pluralize(group.count, "job")}</span>
                      <span className={styles.groupTime}>{ago(group.latestAt, now)}</span>
                    </button>
                    {expanded ? (
                      <ul id={panelId} className={styles.list}>
                        {group.jobs.map((job) => (
                          <Row
                            key={jobKey(job)}
                            nested
                            reveal
                            title={stripProfilePrefix(job.title || job.job_id, name, group.profile)}
                            lead={`failed ${ago(job.failedAt, now)}`}
                            leadTone="danger"
                            sub={job.lastOkAt ? `last ok ${ago(job.lastOkAt, now)}` : null}
                            onClick={close(() => openJob(job.profile, job.job_id))}
                            action={
                              <>
                                <Button size="sm" onClick={close(() => openJob(job.profile, job.job_id))}>Open</Button>
                                {retryable ? (
                                  <Button size="sm" loading={busy.has(jobKey(job))} onClick={() => retry(job)}>Retry</Button>
                                ) : null}
                              </>
                            }
                          />
                        ))}
                      </ul>
                    ) : null}
                  </li>
                );
              })}
            </Section>
          )}
          {shown.running.length > 0 && (
            <Section label="Running" count={shown.running.length}>
              {shown.running.map((run) =>
                run.kind === "workgroup" ? (
                  <Row
                    key={`wg:${run.profile}/${run.workgroup_id}`}
                    tone="accent"
                    color={accentByProfile[run.profile]}
                    glyph={<Fold fold={WORKGROUP_FOLD} color={accentByProfile[run.profile] || undefined} pulse />}
                    title={`${run.name || run.workgroup_id}${run.phase ? ` · #${run.phase}` : ""}`}
                    sub={[
                      profileLabel(run.profile ?? ""),
                      Number.isInteger(run.phases_total) && run.phases_total > 0
                        ? `phase ${Math.min(run.phases_total, (run.phases_done ?? 0) + 1)} of ${run.phases_total}`
                        : run.pipeline || "workgroup",
                    ].join(" · ")}
                    onClick={close(() => onOpenWorkgroup?.(run.profile, run.workgroup_id))}
                  />
                ) : (
                  <Row
                    key={run.job_id ? `job:${run.profile}/${run.job_id}` : `turn:${run.profile}/${run.session_id ?? ""}`}
                    tone="accent"
                    color={accentByProfile[run.profile]}
                    glyph={<Fold fold={foldByProfile[run.profile]} color={accentByProfile[run.profile] || undefined} pulse />}
                    title={run.title || "New session"}
                    sub={[
                      profileLabel(run.profile ?? ""),
                      run.started_at ? relativeTime(toEpochSeconds(run.started_at), now) : null,
                      run.source && run.source !== "chat" ? run.source : null,
                    ].filter(Boolean).join(" · ")}
                    onClick={close(() => run.job_id ? onOpenJob?.(run.profile, run.job_id) : onOpenSession?.(run.profile, run.session_id ?? null))}
                  />
                ),
              )}
            </Section>
          )}
          {shown.upcoming.length > 0 && (
            <Section label="Upcoming" count={shown.upcoming.length}>
              {capped.days.map((day) => (
                <li key={day.start} className={styles.day}>
                  <h4 className={`eyebrow ${styles.dayHead}`}>{`${formatDay(day.start, day.days)} · ${day.total}`}</h4>
                  <ul className={styles.list}>
                    {day.rows.map((job) => (
                      <TimedRow
                        key={`job:${job.profile}/${job.job_id}`}
                        job={job}
                        glyph={<Fold fold={foldByProfile[job.profile]} color={accentByProfile[job.profile] || undefined} />}
                        onClick={close(() => openJob(job.profile, job.job_id))}
                      />
                    ))}
                  </ul>
                </li>
              ))}
              {capped.hidden > 0 ? (
                <li className={styles.more}>
                  <Button size="sm" onClick={() => setShowAllUpcoming(true)}>Show {capped.hidden} more</Button>
                </li>
              ) : null}
            </Section>
          )}
        </div>
      </PanelShell>
    </Scrim>
  );
}
