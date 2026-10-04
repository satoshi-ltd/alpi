import styles from "./ProfileMessage.module.css";

export default function ProfileMessage({
  role = "assistant",   // "user" | "assistant"
  children,
  footer,
}) {
  if (role === "user") {
    return (
      <div className={`msg-row ${styles.userRow}`}>
        <div className={styles.userBubble}>
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
        <div className={styles.assistantFooter}>{footer}</div>
      )}
    </div>
  );
}
