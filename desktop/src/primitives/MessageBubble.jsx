import styles from "./MessageBubble.module.css";

export default function MessageBubble({
  side = "left",
  tint,
  children,
  meta,
  footer,
  maxWidth = "var(--bubble-max)",
}) {
  const isRight = side === "right";
  const background = tint
    ? `color-mix(in srgb, ${tint} 11%, var(--bg-pane))`
    : "var(--hover)";
  return (
    <div className={`msg-row ${styles.root} ${isRight ? styles.rootRight : styles.rootLeft}`}>
      {meta && (
        <div className={`${styles.meta} ${isRight ? styles.metaRight : ""}`.trim()}>
          {meta}
        </div>
      )}
      <div className={styles.bubble} style={{ maxWidth, background }}>
        {children}
      </div>
      {footer && (
        <div className={`msg-actions ${styles.footer} ${isRight ? styles.footerRight : ""}`.trim()}>
          {footer}
        </div>
      )}
    </div>
  );
}
