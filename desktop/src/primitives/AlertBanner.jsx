import Icon from "./Icon.jsx";
import styles from "./AlertBanner.module.css";

export default function AlertBanner({ lead, detail, action = null, onAction = null, disabled = false }) {
  return (
    <div className={styles.banner} role="group" aria-label={lead}>
      <Icon name="triangle-alert" size="md" color="var(--c-danger-text)" className={styles.icon} />
      <span className={styles.text}>
        <span className={styles.lead}>{lead}</span>
        {detail ? <span className={styles.detail}>{detail}</span> : null}
      </span>
      {action ? (
        <button type="button" onClick={onAction} disabled={disabled} className={`alink ${styles.action}`}>
          {action}
        </button>
      ) : null}
    </div>
  );
}
