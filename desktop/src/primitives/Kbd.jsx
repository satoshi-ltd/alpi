import styles from "./Kbd.module.css";

export default function Kbd({ children, className }) {
  return (
    <span
      className={`${styles.kbd} ${className ?? ""}`.trim()}
      aria-hidden
    >
      {children}
    </span>
  );
}
