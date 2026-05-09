import { useEffect, useRef, useState } from "react";
import Button from "../../primitives/Button.jsx";
import Tooltip from "../../primitives/Tooltip.jsx";
import { useNotify } from "../../primitives/Notification.jsx";
import styles from "../Settings.module.css";

export function Section({ title, tooltip, children }) {
  const titleEl = (
    <div
      className={`${styles.sectionTitle} ${tooltip ? styles.sectionTitleHelp : ""}`}
    >
      {title}
      {tooltip && <span className={styles.sectionHelpMark}>?</span>}
    </div>
  );
  return (
    <section className={styles.section}>
      {tooltip ? (
        <Tooltip text={tooltip} direction="down">
          {titleEl}
        </Tooltip>
      ) : (
        titleEl
      )}
      <div className={styles.sectionBody}>{children}</div>
    </section>
  );
}

export function Row({ label, alignTop, children }) {
  return (
    <div
      className={`${styles.row} ${alignTop ? styles.rowAlignTop : ""}`}
    >
      <span className={styles.rowLabel}>{label}</span>
      <div className={styles.rowValue}>{children}</div>
    </div>
  );
}

export function ConfirmButton({
  label,
  confirmLabel,
  disabled,
  loading,
  size,
  onConfirm,
  resetMs = 4000,
}) {
  const [armed, setArmed] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  useEffect(() => {
    if (loading && armed) setArmed(false);
  }, [loading, armed]);

  function click() {
    if (armed) {
      if (timerRef.current) clearTimeout(timerRef.current);
      setArmed(false);
      onConfirm?.();
      return;
    }
    setArmed(true);
    timerRef.current = setTimeout(() => setArmed(false), resetMs);
  }

  return (
    <Button
      size={size}
      variant={armed && !loading ? "danger" : "ghost"}
      active={armed && !loading}
      disabled={disabled}
      loading={loading}
      onClick={click}
    >
      {armed ? confirmLabel : label}
    </Button>
  );
}

export function CopyButton({ value, message }) {
  const notify = useNotify();
  return (
    <Button
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          notify({ message, variant: "success" });
        } catch (e) {
          notify({ message: `Copy failed: ${e}`, variant: "error" });
        }
      }}
    >
      Copy
    </Button>
  );
}
