import styles from "./ProfileMessage.module.css";

export default function ProfileMessage({
  role = "assistant",   // "user" | "assistant"
  accent,
  children,
  footer,
}) {
  if (role === "user") {
    return (
      <div className={`msg-row ${styles.userRow}`}>
        <div
          className={styles.userBubble}
          style={{
            background: `color-mix(in srgb, ${accent || "var(--accent)"} 12%, var(--bg-pane))`,
          }}
        >
          {children}
        </div>
        {footer && <div className={styles.userFooter}>{footer}</div>}
      </div>
    );
  }

  return (
    <div className={`msg-row ${styles.assistantRow}`}>
      <div className="profmsg">{children}</div>
      {footer && (
        <div className={`msg-actions ${styles.assistantFooter}`}>{footer}</div>
      )}
    </div>
  );
}
