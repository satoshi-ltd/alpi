import styles from "./Section.module.css";

export default function Section({ label, kicker, children }) {
  return (
    <section className="ds-section">
      <div className={styles.head}>
        <h3>{label}</h3>
        {kicker && <span className={styles.kicker}>{kicker}</span>}
      </div>
      <div className={styles.body}>{children}</div>
    </section>
  );
}
