import styles from "./DiamondStack.module.css";

export default function DiamondStack({ color, pulse = false, className = "", style }) {
  const rootClass = [styles.root, pulse ? styles.pulsing : "", className]
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
