import Button from "./Button.jsx";
import styles from "./DialogFooter.module.css";

export default function DialogFooter({
  primaryLabel,
  onPrimary,
  primaryDisabled = false,
  primaryLoading = false,
  destructive = false,
  onCancel,
  cancelLabel,
  leading,
}) {
  const hasPrimary = Boolean(primaryLabel);
  const secondaryLabel = cancelLabel || (hasPrimary ? "Cancel" : "Close");
  return (
    <div className={styles.root}>
      {leading && <span className={styles.leading}>{leading}</span>}
      {onCancel && (
        <Button variant="ghost" onClick={onCancel} disabled={primaryLoading}>
          {secondaryLabel}
        </Button>
      )}
      {hasPrimary && (
        <Button
          variant="primary"
          onClick={onPrimary}
          disabled={primaryDisabled || primaryLoading}
          loading={primaryLoading}
          className={destructive ? styles.destructive : ""}
        >
          {primaryLabel}
        </Button>
      )}
    </div>
  );
}
