import { CpuIcon, Dot, ServerIcon, ChevDownIcon, Tip } from "./index.js";
import styles from "./ConnPill.module.css";

const STATUS_COLORS = {
  online: "var(--c-success)",
  connected: "var(--c-success)",
  offline: "var(--c-danger)",
  "auth-failed": "var(--c-warning)",
  probing: "var(--c-warning)",
  unknown: "var(--ink-3)",
};

export default function ConnPill({
  kind = "local",
  name,
  host,
  status = "unknown",
  onClick,
  tipText = "Switch connection",
}) {
  const isOffline = status === "offline" || status === "auth-failed";
  const statusColor = STATUS_COLORS[status] || STATUS_COLORS.unknown;
  return (
    <Tip
      text={isOffline ? "Daemon offline — click to retry" : tipText}
      side="l"
      block
    >
      <button type="button" className="ds-conn-pill" onClick={onClick}>
        <span className={styles.iconWrap}>
          {kind === "local" ? <CpuIcon /> : <ServerIcon />}
          <Dot color={statusColor} pulse={isOffline} className={styles.dot} />
        </span>
        <span className={`col ${styles.col}`}>
          <span className={`name ${styles.name}`}>{name}</span>
          <span
            className={`host ${isOffline ? styles.hostOffline : styles.host}`}
          >
            {isOffline ? "offline · retrying…" : host}
          </span>
        </span>
        <ChevDownIcon className={styles.chev} />
      </button>
    </Tip>
  );
}
