import styles from "./Icon.module.css";

export default function Icon({
  size = 14,
  color = null,
  className = "",
  style = null,
  children,
}) {
  return (
    <span
      className={`${styles.icon} ${className}`}
      style={{
        width: size,
        height: size,
        color: color ?? undefined,
        fill: color ?? undefined,
        ...style,
      }}
      aria-hidden="true"
    >
      {children}
    </span>
  );
}
