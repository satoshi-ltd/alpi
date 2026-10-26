import { CheckIcon, Dot, SkipIcon, XIcon } from "./index.js";
import styles from "./MarkerCard.module.css";

const LABELS = { task: "TASK", working: "WORKING", skip: "SKIP", done: "DONE" };
const CLOSE_LABEL = { blocked: "BLOCKED", skipped: "SKIPPED", preempted: "PREEMPTED" };
const CLOSE_CLASS = {
  blocked: styles.closeBlocked,
  skipped: styles.closeSkipped,
  preempted: styles.closeSkipped,
};

function MarkerIcon({ variant, stale, closeKind }) {
  if (variant === "done") {
    if (closeKind === "blocked") {
      return <SkipIcon size="sm" />;
    }
    if (closeKind === "skipped" || closeKind === "preempted") {
      return <XIcon size="sm" />;
    }
    return <CheckIcon size="sm" />;
  }
  if (variant === "working") {
    return stale ? <span className={styles.bullet} /> : <Dot pulse color="currentColor" />;
  }
  if (variant === "skip") {
    return <SkipIcon size="sm" />;
  }
  return <span className={styles.bullet} />;
}

export default function MarkerCard({
  variant = "task",
  outcome = null,
  side = "left",
  hubColor,
  taskId,
  title,
  children,
  meta,
  footer,
  label,
  stale = false,
  actionsAtRest = false,
}) {
  const isRight = side === "right";
  const hasBody = Boolean(children);
  const compact = !title && !hasBody;
  const closeKind = variant === "done" && outcome && outcome !== "done" ? outcome : null;
  return (
    <div
      id={taskId ? `task-${taskId}` : undefined}
      data-task-marker={variant}
      data-msg-task={taskId || ""}
      className={["msg-row", styles.root, isRight ? styles.rootRight : null, CLOSE_CLASS[closeKind]]
        .filter(Boolean)
        .join(" ")}
    >
      {meta && (
        <div className={`${styles.meta} ${isRight ? styles.metaRight : ""}`.trim()}>
          {meta}
        </div>
      )}
      <div className={`ds-marker ${variant}${compact ? " compact" : ""}`} style={{ "--c": hubColor }}>
        <div className="ey">
          <MarkerIcon variant={variant} stale={stale} closeKind={closeKind} />
          <span>{label || CLOSE_LABEL[closeKind] || LABELS[variant] || variant.toUpperCase()}</span>
        </div>
        {title && <div className="ttl">{title}</div>}
        {hasBody && <div className="body">{children}</div>}
      </div>
      {footer && (
        <div data-rest={actionsAtRest || undefined} className={`msg-actions ${styles.footer} ${isRight ? styles.footerRight : ""}`.trim()}>
          {footer}
        </div>
      )}
    </div>
  );
}
