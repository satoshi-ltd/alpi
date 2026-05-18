import { useMemo, useState } from "react";
import {
  Btn,
  CheckIcon,
  ChevDownIcon,
  Eyebrow,
  Mono,
  SkipIcon,
  Tag,
  Tip,
} from "./index.js";
import { Popover } from "./index.js";
import styles from "./TasksButton.module.css";

function readMarker(body) {
  for (const line of String(body || "").split("\n")) {
    let m = /^(?:@\S+\s+)*#task\s+(.+?)\s*$/i.exec(line);
    if (m) return { kind: "task", text: m[1].trim() };
    m = /^(?:@\S+\s+)*#working(?:\s+(.+?))?\s*$/i.exec(line);
    if (m) return { kind: "working", text: (m[1] ?? "").trim() };
    m = /^(?:@\S+\s+)*#skip(?:\s+(.+?))?\s*$/i.exec(line);
    if (m) return { kind: "skip", text: (m[1] ?? "").trim() };
    m = /^(?:@\S+\s+)*#done\s+(.+?)\s*$/i.exec(line);
    if (m) return { kind: "done", text: m[1].trim() };
  }
  return null;
}

function slugifyTitle(t, fallback) {
  const s = String(t || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 28);
  return s || `task-${fallback}`;
}

function deriveTasks(thread = []) {
  const tasks = [];
  let active = null;
  for (const msg of thread) {
    const mk = readMarker(msg.body);
    if (mk?.kind === "task") {
      active = {
        seq: msg.seq,
        slug: slugifyTitle(mk.text, msg.seq),
        title: mk.text,
        status: "open",
        contributions: 0,
      };
      tasks.push(active);
      continue;
    }
    if (!active) continue;
    if (mk?.kind === "working") {
      active.status = "working";
      continue;
    }
    if (mk?.kind === "done" || mk?.kind === "skip") {
      active.status = mk.kind;
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
  open: "open",
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
  if (status === "working") {
    return (
      <span className={styles.glyphDots} style={{ "--c": color }} aria-hidden>
        <span className={styles.glyphDot} />
        <span className={styles.glyphDot} />
        <span className={styles.glyphDot} />
      </span>
    );
  }
  return <span className={styles.openRing} style={{ borderColor: color }} aria-hidden />;
}

export default function TasksButton({ thread = [], hubColor, onJump }) {
  const [open, setOpen] = useState(false);

  const tasks = useMemo(() => deriveTasks(thread), [thread]);
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
            <span
              className={styles.activeDot}
              style={{ "--c": hubColor }}
              aria-hidden
            />
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
