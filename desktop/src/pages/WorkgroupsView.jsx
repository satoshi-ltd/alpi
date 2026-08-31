import { useMemo, useState } from "react";
import {
  Button,
  DiamondStack,
  Mono,
  PlusIcon,
  RelativeTime,
  SearchIcon,
} from "../primitives/index.js";
import styles from "./WorkgroupsView.module.css";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "queued", label: "Queued" },
  { id: "paused", label: "Paused" },
];

function workgroupState(workgroup, task, busy) {
  if (workgroup.paused) return { id: "paused", label: "Paused" };
  if (workgroup.pipeline_status === "queued") {
    const position = Number(workgroup.queue_position || 0);
    return { id: "queued", label: position ? `Queued · #${position}` : "Queued" };
  }
  if (workgroup.pipeline_status === "blocked") {
    return { id: "error", label: "Needs attention" };
  }
  if (["running", "between"].includes(workgroup.pipeline_status)) {
    return { id: "active", label: "Working" };
  }
  if (workgroup.pipeline_status === "completed") {
    return { id: "idle", label: "Idle" };
  }
  if (task?.state === "error") return { id: "error", label: "Needs attention" };
  if (busy || task?.state === "open") return { id: "active", label: "Working" };
  return { id: "idle", label: "Idle" };
}

function money(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

export default function WorkgroupsView({
  workgroups = [],
  profiles = [],
  taskByWorkgroup = {},
  activityByWorkgroup = {},
  onOpenWorkgroup,
  onNewWorkgroup,
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const accentByProfile = useMemo(
    () => Object.fromEntries(profiles.map((profile) => [profile.name, profile.accent])),
    [profiles],
  );
  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return workgroups
      .map((workgroup) => {
        const key = `${workgroup.profile}/${workgroup.id}`;
        return {
          workgroup,
          key,
          state: workgroupState(
            workgroup,
            taskByWorkgroup[key],
            Boolean(activityByWorkgroup[key]),
          ),
        };
      })
      .filter(({ workgroup, state }) => {
        if (filter === "active" && state.id !== "active" && state.id !== "error") return false;
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
        const leftRank = left.state.id === "active" || left.state.id === "error" ? 0 : left.state.id === "queued" ? 1 : left.state.id === "paused" ? 3 : 2;
        const rightRank = right.state.id === "active" || right.state.id === "error" ? 0 : right.state.id === "queued" ? 1 : right.state.id === "paused" ? 3 : 2;
        return leftRank - rightRank
          || (left.state.id === "queued" && right.state.id === "queued"
            ? Number(left.workgroup.queue_position || 0) - Number(right.workgroup.queue_position || 0)
            : 0)
          || Number(right.workgroup.mtime || 0) - Number(left.workgroup.mtime || 0);
      });
  }, [activityByWorkgroup, filter, query, taskByWorkgroup, workgroups]);
  const summary = useMemo(() => {
    const counts = { active: 0, error: 0, idle: 0, queued: 0, paused: 0 };
    workgroups.forEach((workgroup) => {
      const key = `${workgroup.profile}/${workgroup.id}`;
      const state = workgroupState(
        workgroup,
        taskByWorkgroup[key],
        Boolean(activityByWorkgroup[key]),
      );
      counts[state.id] += 1;
    });
    return counts;
  }, [activityByWorkgroup, taskByWorkgroup, workgroups]);
  const workgroupLabel = `${workgroups.length} workgroup${workgroups.length === 1 ? "" : "s"}`;
  const activityParts = [
    `${summary.active} working`,
    summary.queued ? `${summary.queued} queued` : null,
    `${summary.idle} idle`,
    summary.paused ? `${summary.paused} paused` : null,
    summary.error ? `${summary.error} need attention` : null,
  ].filter(Boolean);

  return (
    <section className={styles.page}>
      <header className={`ds-chat-header ${styles.header}`} data-drag>
        <div className={styles.titleBlock}>
          <div className="title-row">
            <DiamondStack size="md" />
            <h1>Workgroups</h1>
          </div>
          <div className="meta-row">
            <span>{workgroupLabel}</span>
            <span className="sep" aria-hidden />
            <span>{activityParts.join(" · ")}</span>
          </div>
        </div>
        {onNewWorkgroup && (
          <Button icon={<PlusIcon />} onClick={onNewWorkgroup}>New workgroup</Button>
        )}
        <span className="stripe" aria-hidden />
      </header>

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
              <div className={styles.filters} aria-label="Filter workgroups">
                {FILTERS.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={filter === item.id ? styles.filterActive : undefined}
                    onClick={() => setFilter(item.id)}
                    aria-pressed={filter === item.id}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <Mono>{rows.length} of {workgroups.length}</Mono>
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
            {rows.map(({ workgroup, key, state }) => {
              const accent = accentByProfile[workgroup.hub_id ?? workgroup.profile];
              return (
                <button
                  key={key}
                  type="button"
                  className={styles.row}
                  onClick={() => onOpenWorkgroup?.(workgroup)}
                >
                  <span className={styles.identity}>
                    <DiamondStack color={accent} />
                    <strong>{workgroup.name ?? workgroup.id}</strong>
                  </span>
                  <span className={`${styles.status} ${styles[`status_${state.id}`]}`}>
                    <span aria-hidden />
                    {state.label}
                  </span>
                  <Mono tnum>{workgroup.members ?? 0}</Mono>
                  <Mono tnum className={styles.spend}>{money(workgroup.spent_usd)}</Mono>
                  <span className={styles.updated}>
                    {workgroup.mtime ? <RelativeTime ts={workgroup.mtime} /> : "—"}
                  </span>
                </button>
              );
            })}
          </div>

          {rows.length === 0 && (
            <div className={styles.empty}>
              {workgroups.length === 0 ? "No workgroups on this connection." : "No workgroups match this view."}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
