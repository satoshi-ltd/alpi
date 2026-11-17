import { useMemo, useState } from "react";
import { WORKGROUP_SHAPE } from "../../../common/shapes.mjs";
import { accentLookup, workgroupMark, workgroupMarkAccent, workgroupStatusLine } from "../../../common/workgroupMarkState.mjs";
import ChatHeader from "../primitives/ChatHeader.jsx";
import {
  Banner,
  Button,
  Fold,
  PlusIcon,
  RelativeTime,
  SearchIcon,
  EmptyState,
} from "../primitives/index.js";
import styles from "./WorkgroupsView.module.css";
import { SkeletonRows } from "../primitives/Skeleton.jsx";
import { EMPTY } from "../../../common/emptyCopy.mjs";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "queued", label: "Queued" },
  { id: "paused", label: "Paused" },
];

function workgroupState(workgroup, task, busy, mark) {
  if (workgroup.paused) return { id: "paused", label: "Paused" };
  if (workgroup.pipeline_status === "queued") {
    const position = Number(workgroup.queue_position || 0);
    return { id: "queued", label: position ? `Queued · #${position}` : "Queued" };
  }
  if (workgroup.pipeline_status === "blocked") {
    return { id: "needs", label: workgroupStatusLine(mark) ?? "Needs you" };
  }
  if (["running", "between"].includes(workgroup.pipeline_status)) {
    if (mark.step) return { id: "active", label: workgroupStatusLine(mark) };
    return { id: "active", label: task?.state === "open" && task.slug ? `Working · ${task.slug}` : "Working" };
  }
  if (workgroup.pipeline_status === "completed") {
    return { id: "idle", label: "Idle" };
  }
  if (task?.state === "error") return { id: "error", label: "Needs attention" };
  if (busy || task?.state === "open") return { id: "active", label: "Working" };
  return { id: "idle", label: "Idle" };
}

function rowState(workgroup, run, task, busy) {
  const mark = workgroupMark({ workgroup, run, task, busy });
  return { mark, state: workgroupState(workgroup, task, busy, mark) };
}

function money(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

const URGENT = new Set(["active", "needs", "error"]);

function stateRank(stateId) {
  return URGENT.has(stateId) ? 0 : stateId === "queued" ? 1 : 2;
}

export default function WorkgroupsView({
  workgroups = [],
  profiles = [],
  taskByWorkgroup = {},
  activityByWorkgroup = {},
  runByWorkgroup = null,
  onOpenWorkgroup,
  onNewWorkgroup,
  syncing = false,
  stale = false,
  onRefresh,
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const accentByProfile = useMemo(
    () => Object.fromEntries(profiles.map((profile) => [profile.name, profile.accent])),
    [profiles],
  );
  const accentOf = useMemo(() => accentLookup(profiles), [profiles]);
  const rows = useMemo(() => {
    const now = Date.now();
    const needle = query.trim().toLowerCase();
    return workgroups
      .map((workgroup) => {
        const key = `${workgroup.profile}/${workgroup.id}`;
        return {
          workgroup,
          key,
          ...rowState(workgroup, runByWorkgroup?.[key] ?? null, taskByWorkgroup[key], Boolean(activityByWorkgroup[key])),
        };
      })
      .filter(({ workgroup, state }) => {
        if (filter === "active" && !URGENT.has(state.id)) return false;
        if (filter === "queued" && state.id !== "queued") return false;
        if (filter === "paused" && state.id !== "paused") return false;
        if (!needle) return true;
        return [workgroup.name, workgroup.id, workgroup.profile, workgroup.hub_id, state.label]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(needle);
      })
      .sort((left, right) => {
        const leftTime = Number(left.workgroup.mtime || 0);
        const rightTime = Number(right.workgroup.mtime || 0);
        return stateRank(left.state.id) - stateRank(right.state.id)
          || Number(left.workgroup.queue_position || 0) - Number(right.workgroup.queue_position || 0)
          || rightTime - leftTime;
      });
  }, [activityByWorkgroup, filter, query, runByWorkgroup, taskByWorkgroup, workgroups]);
  const summary = useMemo(() => {
    const counts = { active: 0, needs: 0, error: 0, idle: 0, queued: 0, paused: 0 };
    workgroups.forEach((workgroup) => {
      const key = `${workgroup.profile}/${workgroup.id}`;
      const { state } = rowState(workgroup, runByWorkgroup?.[key] ?? null, taskByWorkgroup[key], Boolean(activityByWorkgroup[key]));
      counts[state.id] += 1;
    });
    return counts;
  }, [activityByWorkgroup, runByWorkgroup, taskByWorkgroup, workgroups]);
  const workgroupLabel = `${workgroups.length} workgroup${workgroups.length === 1 ? "" : "s"}`;
  const activityParts = [
    `${summary.active} working`,
    summary.queued ? `${summary.queued} queued` : null,
    `${summary.idle} idle`,
    summary.paused ? `${summary.paused} paused` : null,
    summary.needs ? `${summary.needs} need you` : null,
    summary.error ? `${summary.error} need attention` : null,
  ].filter(Boolean);

  return (
    <section className={styles.page}>
      <ChatHeader
        kind="workgroup"
        id="Workgroups"
        accent="var(--accent)"
        mark={{ seed: "workgroups" }}
        meta={(
          <span className={styles.summary}>
            <span>{workgroupLabel}</span>
            <span>{activityParts.join(" · ")}</span>
          </span>
        )}
        right={onNewWorkgroup ? <Button icon={<PlusIcon />} onClick={onNewWorkgroup}>New workgroup</Button> : null}
      />

      {stale && (
        <Banner kind="warning" action={onRefresh ? "Retry" : null} onAction={onRefresh}>
          {syncing ? "Updating workgroups… Displayed data may be out of date." : "Workgroups may be out of date. Retrying automatically."}
        </Banner>
      )}
      <div className={styles.body}>
        <div className={styles.table}>
          <div className={styles.toolbar}>
            <label className={styles.search}>
              <SearchIcon />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search workgroups…"
                aria-label="Search workgroups"
              />
            </label>
            <div className={styles.toolbarRight}>
              <div className="ds-seg" aria-label="Filter workgroups">
                {FILTERS.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setFilter(item.id)}
                    aria-pressed={filter === item.id}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <span>{rows.length} of {workgroups.length}</span>
            </div>
          </div>

          {rows.length > 0 && (
            <div className={styles.tableHead} aria-hidden>
              <span>Workgroup</span>
              <span>Status</span>
              <span>Members</span>
              <span>Spend</span>
              <span>Updated</span>
            </div>
          )}

          <div className={styles.rows}>
            {rows.map(({ workgroup, key, state, mark }) => {
              const accent = accentByProfile[workgroup.hub_id ?? workgroup.profile];
              return (
                <button
                  key={key}
                  type="button"
                  className={styles.row}
                  onClick={() => onOpenWorkgroup?.(workgroup)}
                >
                  <span className={styles.identity}>
                    <Fold shape={WORKGROUP_SHAPE} color={workgroupMarkAccent(mark, accent, accentOf)} state={mark.state} phase={mark.phase} seed={key} />
                    <span className="sb-name">{workgroup.name ?? workgroup.id}</span>
                  </span>
                  <span className={styles.statusCell}>
                    <span className={`${styles.status} ${styles[`status_${state.id}`]}`}>
                      <span aria-hidden />
                      {state.label}
                    </span>
                    {workgroup.pipeline_note && (
                      <span className={styles.statusNote} title={workgroup.pipeline_note}>{workgroup.pipeline_note}</span>
                    )}
                  </span>
                  <span className="tnum">{workgroup.members ?? 0}</span>
                  <span className={"tnum " + styles.spend}>{money(workgroup.spent_usd)}</span>
                  <span className={styles.updated}>
                    {workgroup.mtime ? <RelativeTime ts={workgroup.mtime} /> : "—"}
                  </span>
                </button>
              );
            })}
          </div>

          {rows.length === 0 && workgroups.length > 0 && (
            <div className={styles.empty}>No workgroups match this view.</div>
          )}
          {workgroups.length === 0 && (syncing ? (
            <SkeletonRows count={3} label="Syncing workgroups" />
          ) : (
            <EmptyState
              shape={WORKGROUP_SHAPE}
              heading={EMPTY.workgroups.title}
              subtitle={EMPTY.workgroups.hint}
              action={onNewWorkgroup ? { label: "New workgroup", onClick: onNewWorkgroup } : null}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
