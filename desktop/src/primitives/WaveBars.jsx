import styles from "./WaveBars.module.css";

export default function WaveBars({ accent, active = false, className = "" }) {
  return (
    <span
      className={`${styles.bars} ${className}`}
      style={{ "--c": accent || "var(--accent)" }}
      data-active={active ? "" : undefined}
      aria-hidden
    >
      <span />
      <span />
      <span />
    </span>
  );
}
