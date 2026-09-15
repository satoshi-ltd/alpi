import { CpuIcon, Dot, ServerIcon, ChevDownIcon, Tip } from "./index.js";
import { RATE_LIMITED, RATE_LIMITED_MESSAGE } from "../lib/connection-status.js";
import styles from "./ConnPill.module.css";

const STATUS_COLORS = {
  online: "var(--c-success)",
  connected: "var(--c-success)",
  offline: "var(--c-danger)",
  disabled: "var(--ink-3)",
  "auth-failed": "var(--c-warning)",
  [RATE_LIMITED]: "var(--c-warning)",
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
  const isDisabled = status === "disabled";
  const isOffline = status === "offline" || status === "auth-failed";
  const isProbing = status === "probing";
  const isRateLimited = status === RATE_LIMITED;
  const statusColor = STATUS_COLORS[status] || STATUS_COLORS.unknown;
  return (
    <Tip
      text={
        isDisabled
          ? "Connection disabled by host"
          : isRateLimited
          ? RATE_LIMITED_MESSAGE
          : isOffline
          ? "Daemon offline — click to retry"
          : isProbing
            ? "Connecting…"
            : tipText
      }
      side="l"
      block
    >
      <button type="button" className="ds-conn-pill" onClick={onClick}>
        <span className={styles.iconWrap}>
          {kind === "local" ? <CpuIcon /> : <ServerIcon />}
          <Dot
            color={statusColor}
            pulse={isOffline || isProbing}
            className={styles.dot}
          />
        </span>
        <span className={`col ${styles.col}`}>
          <span className={`name ${styles.name}`}>{name}</span>
          <span
            className={`host ${
              isOffline
                ? styles.hostOffline
                : isProbing
                  ? styles.hostProbing
                  : styles.host
            }`}
          >
            {isDisabled
              ? "disabled"
              : isRateLimited
                ? "rate limited · retrying in a minute"
              : isOffline
                ? "offline · retrying…"
                : isProbing
                  ? "connecting…"
                  : host}
          </span>
        </span>
        <ChevDownIcon className={styles.chev} />
      </button>
    </Tip>
  );
}
