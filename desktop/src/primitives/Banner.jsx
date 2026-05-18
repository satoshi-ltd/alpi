import Dot from "./Dot.jsx";
import styles from "./Banner.module.css";

const KIND_COLOR = {
  info: "var(--ink-3)",
  success: "var(--c-success)",
  warning: "var(--c-warning)",
  danger: "var(--c-danger)",
};

export default function Banner({
  kind = "info",
  pulsing = false,
  children,
  action,
  onAction,
}) {
  const color = KIND_COLOR[kind] ?? KIND_COLOR.info;
  return (
    <div className={`banner is-${kind}`} role={kind === "danger" ? "alert" : "status"}>
      <Dot color={color} pulse={pulsing} className={styles.dot} />
      <span className={styles.body}>{children}</span>
      {action && (
        <button
          type="button"
          onClick={onAction}
          className={`alink ${styles.action}`}
        >
          {action}
        </button>
      )}
    </div>
  );
}

export { Dot };
