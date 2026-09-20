import { forwardRef } from "react";
import { buttonDefaults, buttonHeights, buttonVariants } from "../../../common/button.mjs";
import Tooltip from "./Tooltip.jsx";
import styles from "./Button.module.css";

const Button = forwardRef(function Button({
  variant = buttonDefaults.desktop.variant,
  size = buttonDefaults.desktop.size,
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
  fullWidth = false,
  className: extraClassName = "",
  ...rest
}, ref) {
  variant = buttonVariants.includes(variant) ? variant : buttonDefaults.desktop.variant;
  size = Object.hasOwn(buttonHeights, size) ? size : buttonDefaults.desktop.size;
  const isIconOnly = !!icon && !children;
  const isDisabled = disabled || loading;
  const className = [
    styles.button,
    styles[variant],
    size === "sm" ? styles.sm : null,
    size === "lg" ? styles.lg : null,
    size === "hero" ? styles.hero : null,
    isIconOnly ? styles.iconOnly : styles.withLabel,
    active ? styles.active : null,
    loading ? styles.loading : null,
    fullWidth ? styles.fullWidth : null,
    extraClassName || null,
  ]
    .filter(Boolean)
    .join(" ");

  const showTooltip = !!title && !isDisabled;

  const button = (
    <button
      {...rest}
      ref={ref}
      type={type}
      className={className}
      style={style}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      onClick={onClick}
      aria-label={rest["aria-label"] ?? (isIconOnly ? title : undefined)}
    >
      {loading && <span className={styles.spinner} aria-hidden />}
      {icon && !loading && <span className={styles.icon}>{icon}</span>}
      {children}
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
});

export default Button;
