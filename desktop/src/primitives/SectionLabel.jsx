import Eyebrow from "./Eyebrow.jsx";
import styles from "./SectionLabel.module.css";

export default function SectionLabel({ children, right }) {
  return (
    <div className={styles.root}>
      <Eyebrow className={styles.label}>{children}</Eyebrow>
      {right}
    </div>
  );
}
