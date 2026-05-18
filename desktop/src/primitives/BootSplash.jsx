import AlpiSilhouette from "./AlpiSilhouette.jsx";
import styles from "./BootSplash.module.css";

export default function BootSplash({ message = "Connecting to daemon…" }) {
  return (
    <div className={styles.root}>
      <AlpiSilhouette className={styles.glyph} />
      <span className={styles.msg}>{message}</span>
    </div>
  );
}
