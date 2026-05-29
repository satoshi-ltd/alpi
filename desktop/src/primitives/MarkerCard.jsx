import { CheckIcon, Diamond, SkipIcon } from "./index.js";
import styles from "./MarkerCard.module.css";

const LABELS = { task: "TASK", working: "WORKING", skip: "SKIP", done: "DONE" };

function MarkerIcon({ variant, stale }) {
  if (variant === "done") {
    return <CheckIcon style={{ width: 11, height: 11, strokeWidth: 2.2 }} />;
  }
  if (variant === "working") {
    return stale ? <span className={styles.bullet} /> : <Diamond pulse />;
  }
  if (variant === "skip") {
    return <SkipIcon style={{ width: 11, height: 11, strokeWidth: 2 }} />;
  }
  return <span className={styles.bullet} />;
}

export default function MarkerCard({
  variant = "task",
  side = "left",
  hubColor,
  taskId,
  title,
  children,
  meta,
  footer,
  label,
  stale = false,
}) {
  const isRight = side === "right";
  return (
    <div
      id={taskId ? `task-${taskId}` : undefined}
      data-task-marker={variant}
      data-msg-task={taskId || ""}
      className={`msg-row ${styles.root} ${isRight ? styles.rootRight : ""}`.trim()}
    >
      {meta && (
        <div className={`${styles.meta} ${isRight ? styles.metaRight : ""}`.trim()}>
          {meta}
        </div>
      )}
      <div className={`ds-marker ${variant}`} style={{ "--c": hubColor }}>
        <div className="ey">
          <MarkerIcon variant={variant} stale={stale} />
          <span>{label || LABELS[variant] || variant.toUpperCase()}</span>
        </div>
        {title && <div className="ttl">{title}</div>}
        <div className="body">{children}</div>
      </div>
      {footer && (
        <div className={`msg-actions ${styles.footer} ${isRight ? styles.footerRight : ""}`.trim()}>
          {footer}
        </div>
      )}
    </div>
  );
}
