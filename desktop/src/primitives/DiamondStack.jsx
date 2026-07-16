import styles from "./DiamondStack.module.css";

export default function DiamondStack({ color, size, pulse = false, className = "", style }) {
  const rootClass = [styles.root, size === "md" ? styles.md : "", pulse ? styles.pulsing : "", className]
    .filter(Boolean)
    .join(" ");
  return (
    <span
      className={rootClass}
      aria-hidden
      style={{ "--c": color || undefined, ...style }}
    >
      <span className={`${styles.dot} ${styles.back}`} />
      <span className={`${styles.dot} ${styles.front}`} />
    </span>
  );
}
