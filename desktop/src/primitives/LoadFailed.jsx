import Button from "./Button.jsx";
import styles from "./LoadFailed.module.css";

export default function LoadFailed({ label, error, onRetry, inline = false }) {
  const message = `Couldn't load ${label}`;
  if (inline) {
    return (
      <span className={styles.inline} role="alert">
        <span>{message}</span>
        {onRetry && (
          <button type="button" className="alink" onClick={onRetry}>Retry</button>
        )}
      </span>
    );
  }
  return (
    <div className={styles.card} role="alert">
      <div className={styles.title}>{message}</div>
      {error && <div className={styles.detail}>{String(error)}</div>}
      {onRetry && <Button onClick={onRetry}>Retry</Button>}
    </div>
  );
}
