import styles from "./DiamondStack.module.css";

export default function DiamondStack({ color, className = "", style }) {
  return (
    <span
      className={`${styles.root} ${className}`.trim()}
      aria-hidden
      style={{ "--c": color || undefined, ...style }}
    >
      <span className={`${styles.dot} ${styles.back}`} />
      <span className={`${styles.dot} ${styles.front}`} />
    </span>
  );
}
