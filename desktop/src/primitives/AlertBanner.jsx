import Button from "./Button.jsx";
import Icon from "./Icon.jsx";
import styles from "./AlertBanner.module.css";

export default function AlertBanner({ lead, detail, action = null, onAction = null, disabled = false }) {
  return (
    <div className={styles.banner} role="group" aria-label={lead}>
      <Icon name="triangle-alert" size="md" className={styles.icon} aria-hidden />
      <span className={styles.text}>
        <span className={styles.lead}>{lead}</span>
        {detail ? <span className={styles.detail}>{detail}</span> : null}
      </span>
      {action ? <Button size="sm" variant="secondary" onClick={onAction} disabled={disabled}>{action}</Button> : null}
    </div>
  );
}
