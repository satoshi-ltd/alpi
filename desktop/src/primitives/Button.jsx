import { forwardRef } from "react";
import { buttonDefaults, buttonHeights, buttonVariants } from "../../../common/button.mjs";
import Tip from "./Tip.jsx";
import { SpinnerIcon } from "./icons.jsx";
import styles from "./Button.module.css";

export function tipSideFor(direction = "down", align = "center") {
  if (direction === "left") return "l";
  if (direction === "right") return "r";
  const up = direction === "up";
  if (align === "start") return up ? "up-l" : "l";
  if (align === "end") return up ? "up-r" : "r";
  return up ? "up" : "down";
}

const Button = forwardRef(function Button({
  variant = buttonDefaults.desktop.variant,
  size = buttonDefaults.desktop.size,
  icon,
  iconOnly = false,
  tip,
  tipSide,
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
  const isIconOnly = iconOnly || (!!icon && !children);
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

  const tipText = tip ?? title;
  const accessibleName = rest["aria-label"] ?? (isIconOnly ? tipText : undefined);

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
      aria-label={accessibleName}
    >
      {loading && <SpinnerIcon className={styles.spinner} />}
      {icon && !loading && <span className={styles.icon}>{icon}</span>}
      {children}
    </button>
  );

  if (tip) {
    return <Tip text={tip} side={tipSide ?? "down"}>{button}</Tip>;
  }
  if (title && !isDisabled) {
    return (
      <Tip text={title} side={tipSide ?? tipSideFor(tooltipDirection, tooltipAlign)} escape block={fullWidth}>
        {button}
      </Tip>
    );
  }
  return button;
});

export default Button;
