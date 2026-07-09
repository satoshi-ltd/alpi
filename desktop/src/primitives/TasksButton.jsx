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
} from "./index.js";
import { Popover } from "./index.js";
import styles from "./TasksButton.module.css";

const TASK_OPEN_RE = /^(?:@\S+\s+)*#task\s+#([A-Za-z0-9][A-Za-z0-9_-]{0,63})(?:\s+(.+?))?\s*$/i;
const DONE_LINE_RE = /^(?:@\S+\s+)*#done\s+(.+?)\s*$/i;

function readMarker(body) {
  const lines = String(body || "").split("\n");
  // Both #task and #done in one post → prose, no lifecycle event (mirrors alpi parse_post ambiguity rule).
  if (lines.some((l) => TASK_OPEN_RE.test(l)) && lines.some((l) => DONE_LINE_RE.test(l))) {
    return null;
  }
  for (const line of lines) {
    let m = TASK_OPEN_RE.exec(line);
    if (m) {
      return {
        kind: "task",
        slug: m[1].toLowerCase(),
        text: (m[2] ?? "").trim(),
      };
    }
    m = /^(?:@\S+\s+)*#working(?:\s+(.+?))?\s*$/i.exec(line);
    if (m) return { kind: "working", text: (m[1] ?? "").trim() };
    m = /^(?:@\S+\s+)*#skip(?:\s+(.+?))?\s*$/i.exec(line);
    if (m) return { kind: "skip", text: (m[1] ?? "").trim() };
    m = DONE_LINE_RE.exec(line);
    if (m) return { kind: "done", text: m[1].trim() };
  }
  return null;
}

// Only the hub opens (`#task`) and closes (`#done`) tasks. A member's `#skip`/`#working` are round signals that never touch task lifecycle. "skip" status here means preempted: the hub opened a new `#task` before closing this one with `#done` (alpi/alp/tasks.py fold_tasks).
export function deriveTasks(thread = [], hubPubkey = null) {
  const tasks = [];
  let active = null;
  for (const msg of thread) {
    const mk = readMarker(msg.body);
    const fromHub = !hubPubkey || msg.from_pubkey === hubPubkey;
    if (mk?.kind === "task" && fromHub) {
      if (active) active.status = "skip";
      active = {
        seq: msg.seq,
        slug: mk.slug,
        title: mk.text,
        status: "working",
        contributions: 0,
      };
      tasks.push(active);
      continue;
    }
    if (!active) continue;
    if (mk?.kind === "done" && fromHub) {
      active.status = "done";
      active = null;
      continue;
    }
    active.contributions++;
  }
  return tasks;
}

const STATE_LABEL = {
  done: "done",
  skip: "skipped",
  working: "working",
};

function StatusGlyph({ status, color }) {
  if (status === "done") {
    return (
      <CheckIcon style={{ width: 14, height: 14, strokeWidth: 2.2, color }} />
    );
  }
  if (status === "skip") {
    return (
      <SkipIcon
        style={{ width: 13, height: 13, strokeWidth: 2, color: "var(--c-warning)" }}
      />
    );
  }
  return <Dot pulse color={color} />;
}

export default function TasksButton({ thread = [], hubColor, hubPubkey = null, openTick = 0, onJump }) {
  const [open, setOpen] = useState(false);
  const mountedRef = useRef(false);

  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      return;
    }
    if (openTick > 0) setOpen(true);
  }, [openTick]);

  const tasks = useMemo(() => deriveTasks(thread, hubPubkey), [thread, hubPubkey]);
  const total = tasks.length;
  const closed = tasks.filter((t) => t.status === "done" || t.status === "skip")
    .length;
  const active = tasks.find((t) => !["done", "skip"].includes(t.status));
  const activeLabel = active ? active.title || active.slug : null;
  const truncated =
    activeLabel && activeLabel.length > 32
      ? `${activeLabel.slice(0, 32).trim()}…`
      : activeLabel;

  const triggerLabel = active
    ? truncated
    : total > 0
      ? "All tasks resolved"
      : "No tasks yet";
  const tipText = active
    ? "Active #task · click for history"
    : total > 0
      ? "All tasks resolved · click for history"
      : "Direct @hub to open a #task";
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
          ) : total > 0 ? (
            <CheckIcon
              style={{ width: 13, height: 13, strokeWidth: 2.2, color: hubColor || "var(--c-success)" }}
            />
          ) : (
            <span className={styles.openRing} aria-hidden />
          )}
          <span className={styles.triggerLabel}>{triggerLabel}</span>
          {total > 0 && (
            <Mono className={`tnum ${styles.triggerCount}`}>
              {closed}/{total}
            </Mono>
          )}
          <ChevDownIcon className={styles.chev} />
        </Btn>
      </Tip>

      <Popover open={open} onClose={() => setOpen(false)} width="var(--pop-lg)" align="right">
        <div className={styles.head}>
          <div className={styles.headTitle}>
            <Eyebrow>{headEyebrow}</Eyebrow>
            {total > 0 && (
              <Tag>
                {closed}/{total} done
              </Tag>
            )}
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
                  <span className={styles.metaSep}>·</span>
                  <Mono className="tnum">
                    {t.contributions} msg{t.contributions === 1 ? "" : "s"}
                  </Mono>
                  <span className={styles.metaSep}>·</span>
                  <span>{STATE_LABEL[t.status] || t.status}</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      </Popover>
    </span>
  );
}
