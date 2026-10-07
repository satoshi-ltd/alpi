import Busy from "./Busy.jsx";
import styles from "./BootSplash.module.css";

export default function BootSplash({ message = "Reaching the daemon", active = true }) {
  return (
    <div className={styles.root}>
      <Busy active={active} page label={message} />
    </div>
  );
}
