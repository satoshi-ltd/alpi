import Button from "../../primitives/Button.jsx";
import { useNotify } from "../../primitives/Notification.jsx";
import { Section as DSSection, Field as DSField } from "../../primitives/SettingsLayout.jsx";
import { Tip } from "../../primitives/index.js";
import styles from "./Settings.module.css";

export function Section({ title, tooltip, children }) {
  const inner = (
    <>
      {title}
      {tooltip && (
        <span className={styles.sectionHelpMark} aria-label="help">
          ?
        </span>
      )}
    </>
  );
  const label = tooltip ? (
    <Tip text={tooltip} side="down">
      <span style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-3)", cursor: "help" }}>
        {inner}
      </span>
    </Tip>
  ) : (
    inner
  );
  return <DSSection label={label}>{children}</DSSection>;
}

export function Row({ label, alignTop, children }) {
  return (
    <DSField label={label} align={alignTop ? "top" : "center"}>
      {children}
    </DSField>
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
