import styles from "./ProgressBar.module.css";

export default function ProgressBar({ value, max, cells = 8, accent }) {
  const safeMax = max > 0 ? max : 0;
  const ratio = safeMax > 0 ? Math.min(1, Math.max(0, value / safeMax)) : 0;
  const pct = Math.round(ratio * 100);
  const fillStyle = {
    width: `${pct}%`,
  };
  if (accent) fillStyle.background = accent;
  return (
    <span className={styles.bar} role="progressbar" aria-valuenow={pct}>
      <span className={styles.dots}>{"░".repeat(cells)}</span>
      <span className={styles.fill} style={fillStyle} />
    </span>
  );
}
