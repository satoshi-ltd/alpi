import Dot from "./Dot.jsx";
import Icon from "./Icon.jsx";
import styles from "./Banner.module.css";

const DOT_COLOR = {
  info: "var(--ink-3)",
  success: "var(--c-success-text)",
};

const GLYPH_COLOR = {
  warning: "var(--c-warning-text)",
  danger: "var(--c-danger-text)",
};

export default function Banner({
  kind = "info",
  pulsing = false,
  children,
  action,
  onAction,
}) {
  const tone = DOT_COLOR[kind] || GLYPH_COLOR[kind] ? kind : "info";
  return (
    <div className={`banner is-${tone}`} role={tone === "danger" ? "alert" : "status"}>
      {GLYPH_COLOR[tone] ? (
        <Icon name="triangle-alert" size="sm" color={GLYPH_COLOR[tone]} className={`${styles.glyph} ${pulsing ? "pulse-glyph" : ""}`.trim()} />
      ) : (
        <Dot color={DOT_COLOR[tone]} pulse={pulsing} className={styles.dot} />
      )}
      <span className={styles.body}>{children}</span>
      {action && (
        <button type="button" onClick={onAction} className={`alink ${styles.action}`}>
          {action}
        </button>
      )}
    </div>
  );
}

export { Dot };
