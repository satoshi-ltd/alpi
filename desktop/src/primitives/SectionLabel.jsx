import styles from "./SectionLabel.module.css";

export default function SectionLabel({ children, right }) {
  return (
    <div className={styles.root}>
      <span className={`sb-eyebrow ${styles.label}`.trim()}>{children}</span>
      {right}
    </div>
  );
}
