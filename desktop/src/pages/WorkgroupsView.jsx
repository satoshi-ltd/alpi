import { useMemo, useState } from "react";
import { WORKGROUP_SHAPE } from "../../../common/shapes.mjs";
import { accentLookup, workgroupMarkAccent } from "../../../common/workgroupMarkState.mjs";
import { WORKGROUP_FILTERS, filterCounts, groupWorkgroupRows, inFilter, noMatchLine, stateRank, workgroupRowState, workgroupStatusLabel } from "../../../common/workgroupList.mjs";
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

function money(value) {
  return `$${Number(value || 0).toFixed(2)}`;
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
  const all = useMemo(() => workgroups.map((workgroup) => {
    const key = `${workgroup.profile}/${workgroup.id}`;
    return {
      workgroup,
      key,
      ...workgroupRowState({ workgroup, run: runByWorkgroup?.[key] ?? null, task: taskByWorkgroup[key], busy: Boolean(activityByWorkgroup[key]) }),
    };
  }), [activityByWorkgroup, runByWorkgroup, taskByWorkgroup, workgroups]);
  const counts = useMemo(() => filterCounts(all.map(({ state }) => state.id)), [all]);
  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return all
      .filter(({ workgroup, state }) => {
        if (!inFilter(state.id, filter)) return false;
        if (!needle) return true;
        return [workgroup.name, workgroup.id, workgroup.profile, workgroup.hub_id, state.label]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(needle);
      })
      .sort((left, right) => stateRank(left.state.id) - stateRank(right.state.id)
        || Number(left.workgroup.queue_position || 0) - Number(right.workgroup.queue_position || 0)
        || Number(right.workgroup.mtime || 0) - Number(left.workgroup.mtime || 0));
  }, [all, filter, query]);
  const groups = useMemo(() => {
    if (filter === "all") return groupWorkgroupRows(rows);
    return rows.length ? [{ id: filter, label: null, rows }] : [];
  }, [filter, rows]);

  function renderRow({ workgroup, key, state, mark }) {
    const accent = accentByProfile[workgroup.hub_id ?? workgroup.profile];
    const label = workgroupStatusLabel(state);
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
          {label && (
            <span className={`${styles.status} ${styles[`status_${state.id}`]}`} title={label}>
              <span className={styles.dot} aria-hidden />
              <span className={styles.statusText}>{label}</span>
            </span>
          )}
          {workgroup.pipeline_note && (
            <span className={styles.statusNote} title={workgroup.pipeline_note}>{workgroup.pipeline_note}</span>
          )}
        </span>
        <span className={"tnum " + styles.num}>{workgroup.members ?? 0}</span>
        <span className={"tnum " + styles.num}>{money(workgroup.spent_usd)}</span>
        <span className={styles.updated}>
          {workgroup.mtime ? <RelativeTime ts={workgroup.mtime} /> : "—"}
        </span>
      </button>
    );
  }

  return (
    <section className={styles.page}>
      <ChatHeader
        kind="workgroup"
        id="Workgroups"
        accent="var(--accent)"
        mark={{ seed: "workgroups" }}
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
                {WORKGROUP_FILTERS.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setFilter(item.id)}
                    aria-pressed={filter === item.id}
                    aria-label={`${item.label}, ${counts[item.id]}`}
                    disabled={counts[item.id] === 0 && filter !== item.id}
                  >
                    {item.label}
                    <span className={styles.segCount} aria-hidden>{counts[item.id]}</span>
                  </button>
                ))}
              </div>
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
            {groups.map((group) => (
              <div key={group.id} role="group" aria-label={group.label ?? undefined}>
                {group.label && (
                  <div className={`${styles.groupHead} ${group.id === "needs" ? styles.groupNeeds : ""}`}>
                    {group.label}
                    <span className={styles.groupCount}>{group.rows.length}</span>
                  </div>
                )}
                {group.rows.map(renderRow)}
              </div>
            ))}
          </div>

          {rows.length === 0 && workgroups.length > 0 && (
            <div className={styles.empty}>{noMatchLine(filter, query)}</div>
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
