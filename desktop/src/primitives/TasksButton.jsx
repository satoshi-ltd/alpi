import { useEffect, useMemo, useRef, useState } from "react";
import {
  Btn,
  CheckIcon,
  ChevDownIcon,
  Dot,
  Eyebrow,
  Mono,
  SkipIcon,
  Tag,
  Tip,
  XIcon,
} from "./index.js";
import { Popover } from "./index.js";
import { deriveTasks } from "../lib/workgroup-tasks.js";
import styles from "./TasksButton.module.css";

const CLOSED = ["done", "skipped", "blocked", "preempted"];

function summarize(tasks) {
  const closed = tasks.filter((t) => CLOSED.includes(t.status));
  const active = tasks.find((t) => !CLOSED.includes(t.status)) ?? null;
  const last = closed[closed.length - 1] ?? null;
  const stillBlocked = last?.status === "blocked" ? last : null;
  const allGreen = closed.every((t) => t.status === "done");
  const outcome = tasks.length === 0 || active
    ? null
    : stillBlocked
      ? "blocked"
      : allGreen
        ? "done"
        : "closed";
  return {
    total: tasks.length,
    closedCount: closed.length,
    blockedCount: stillBlocked ? 1 : 0,
    lastBlocked: stillBlocked,
    allGreen,
    active,
    outcome,
  };
}

const RESOLVED_LABEL = { done: "All tasks resolved", closed: "All tasks closed" };
const RESOLVED_TIP = {
  blocked: "A task closed blocked · click for history",
  done: "All tasks resolved · click for history",
  closed: "All tasks closed · click for history",
};
const GLYPH_STATUS = { blocked: "blocked", done: "done", closed: "skipped" };

function StatusGlyph({ status, color }) {
  if (status === "done") {
    return (
      <CheckIcon style={{ width: 14, height: 14, strokeWidth: 2.2, color }} />
    );
  }
  if (status === "blocked") {
    return (
      <SkipIcon
        style={{ width: 13, height: 13, strokeWidth: 2, color: "var(--c-danger)" }}
      />
    );
  }
  if (status === "skipped" || status === "preempted") {
    return (
      <XIcon
        style={{ width: 13, height: 13, strokeWidth: 2, color: "var(--c-warning)" }}
      />
    );
  }
  return <Dot pulse color={color} />;
}

export default function TasksButton({
  thread = [],
  tasks: folded = null,
  hubColor,
  hubPubkey = null,
  openTick = 0,
  onJump,
  historyCapped = false,
}) {
  const [open, setOpen] = useState(false);
  const mountedRef = useRef(false);

  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      return;
    }
    if (openTick > 0) setOpen(true);
  }, [openTick]);

  // The local derivation only sees the loaded tail, so folded rows win whenever the daemon answered.
  const derived = useMemo(() => deriveTasks(thread, hubPubkey), [thread, hubPubkey]);
  const tasks = folded ?? derived;
  const { total, closedCount, blockedCount, lastBlocked, allGreen, active, outcome } =
    useMemo(() => summarize(tasks), [tasks]);
  const activeLabel = active ? active.title || active.slug : null;
  const truncated =
    activeLabel && activeLabel.length > 32
      ? `${activeLabel.slice(0, 32).trim()}…`
      : activeLabel;

  const triggerLabel = active
    ? truncated
    : outcome === "blocked"
      ? `Blocked at #${lastBlocked.slug}`
      : RESOLVED_LABEL[outcome] ?? "No tasks yet";
  const tipText = active
    ? "Active #task · click for history"
    : RESOLVED_TIP[outcome] ?? "Direct @hub to open a #task";
  const countLabel = blockedCount > 0
    ? `${closedCount}/${total} closed · ${blockedCount} blocked`
    : allGreen
      ? `${closedCount}/${total} done`
      : `${closedCount}/${total} closed`;
  // The fold ships only the last 20 closes; never present a capped window as the whole history.
  const historyLabel = historyCapped ? `${countLabel} · recent history` : countLabel;
  const headEyebrow = active
    ? "Active task"
    : total > 0
      ? "Task history"
      : "Tasks";
  const headHelp = active
    ? "The hub opens one #task at a time and closes it with #done."
    : "Open a new task — direct @hub and your input becomes a #task.";
  const c = hubColor || "var(--ink-3)";

  return (
    <span className={styles.root}>
      <Tip text={tipText} side="r">
        <Btn variant="ghost" onClick={() => setOpen((o) => !o)} className={styles.trigger}>
          {active ? (
            <Dot pulse color={hubColor} />
          ) : outcome ? (
            <StatusGlyph
              status={GLYPH_STATUS[outcome]}
              color={hubColor || "var(--c-success)"}
            />
          ) : (
            <span className={styles.openRing} aria-hidden />
          )}
          <span className={styles.triggerLabel}>{triggerLabel}</span>
          {total > 0 && (
            <Mono className={`tnum ${styles.triggerCount}`}>
              {closedCount}/{total}
            </Mono>
          )}
          <ChevDownIcon className={styles.chev} />
        </Btn>
      </Tip>

      <Popover open={open} onClose={() => setOpen(false)} width="var(--pop-lg)" align="right">
        <div className={styles.head}>
          <div className={styles.headTitle}>
            <Eyebrow>{headEyebrow}</Eyebrow>
            {total > 0 && <Tag>{historyLabel}</Tag>}
          </div>
          <p className={styles.headHelp}>{headHelp}</p>
        </div>
        <div className={styles.list}>
          {total === 0 && <div className={styles.empty}>no #task yet</div>}
          {tasks.map((t) => (
            <button
              key={t.seq}
              type="button"
              className={styles.row}
              onClick={() => {
                onJump?.(t.seq);
                setOpen(false);
              }}
            >
              <span className={styles.glyphSlot}>
                <StatusGlyph status={t.status} color={c} />
              </span>
              <div className={styles.rowBody}>
                <div className={styles.title}>{t.title || t.slug}</div>
                <div className={styles.meta}>
                  <Mono>#{t.slug}</Mono>
                  {t.contributions != null && (
                    <>
                      <span className={styles.metaSep}>·</span>
                      <Mono className="tnum">
                        {t.contributions} msg{t.contributions === 1 ? "" : "s"}
                      </Mono>
                    </>
                  )}
                  <span className={styles.metaSep}>·</span>
                  <span>{t.status}</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      </Popover>
    </span>
  );
}
