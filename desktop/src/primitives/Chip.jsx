import Tooltip from "./Tooltip.jsx";
import styles from "./Chip.module.css";

export default function Chip({
  state,
  size = "md",
  accent,
  activity,
  tooltip,
  onClick,
  disabled,
  children,
}) {
  // Disabled chips render as inert spans.
  const interactive = !!onClick && !disabled;
  const className = [
    styles.chip,
    size === "sm" ? styles.sm : null,
    accent ? styles.tinted : null,
    !accent && state === "on" ? styles.on : null,
    !accent && state === "off" ? styles.off : null,
    !accent && state === "error" ? styles.errorState : null,
    !accent && state === "warn" ? styles.warnState : null,
    interactive ? styles.clickable : null,
    disabled ? styles.disabled : null,
    activity ? styles.busy : null,
  ]
    .filter(Boolean)
    .join(" ");

  const indicator = accent
    ? null
    : activity
      ? <span className={styles.spinner} aria-hidden />
      : state
        ? <span className={styles.dot} />
        : null;

  const inlineStyle = accent
    ? {
        backgroundColor: `color-mix(in srgb, ${accent} 18%, transparent)`,
      }
    : undefined;

  const inner = interactive ? (
    <button
      type="button"
      className={className}
      style={inlineStyle}
      onClick={onClick}
    >
      {indicator}
      {children}
    </button>
  ) : (
    <span className={className} style={inlineStyle}>
      {indicator}
      {children}
    </span>
  );

  return tooltip ? <Tooltip text={tooltip}>{inner}</Tooltip> : inner;
}
