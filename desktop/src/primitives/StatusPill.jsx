import styles from "./StatusPill.module.css";

const TONE = { on: styles.on, off: styles.off, bad: styles.bad };

export default function StatusPill({ tone = "off", title, children }) {
  return (
    <span className={`${styles.pill} ${TONE[tone] ?? styles.off}`} title={title || undefined}>
      <span className={styles.dot} aria-hidden />
      {children}
    </span>
  );
}
