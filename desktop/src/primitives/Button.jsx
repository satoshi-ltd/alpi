import Tooltip from "./Tooltip.jsx";
import styles from "./Button.module.css";

export default function Button({
  variant = "ghost",
  size = "md",
  icon,
  children,
  disabled = false,
  loading = false,
  onClick,
  title,
  tooltipDirection = "down",
  tooltipAlign = "center",
  type = "button",
  active = false,
  style,
}) {
  const isIconOnly = !!icon && !children;
  const isDisabled = disabled || loading;
  const className = [
    styles.button,
    styles[variant],
    size === "sm" ? styles.sm : null,
    size === "xs" ? styles.xs : null,
    isIconOnly ? styles.iconOnly : styles.withLabel,
    active ? styles.active : null,
    loading ? styles.loading : null,
  ]
    .filter(Boolean)
    .join(" ");

  const showTooltip = !!title && !isDisabled;

  const button = (
    <button
      type={type}
      className={className}
      style={style}
      disabled={isDisabled}
      onClick={onClick}
      aria-label={isIconOnly ? title : undefined}
    >
      {loading && <span className={styles.spinner} aria-hidden />}
      {icon && !loading && <span className={styles.icon}>{icon}</span>}
      {children && <span className={styles.label}>{children}</span>}
    </button>
  );

  return (
    <Tooltip
      text={showTooltip ? title : null}
      direction={tooltipDirection}
      align={tooltipAlign}
    >
      {button}
    </Tooltip>
  );
}
