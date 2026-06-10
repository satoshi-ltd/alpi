import Button from "../../primitives/Button.jsx";
import { useNotify } from "../../primitives/Notification.jsx";
import { Section as DSSection, Field as DSField } from "../../primitives/SettingsLayout.jsx";
import styles from "./Settings.module.css";
import { copyText } from "../../lib/clipboard.js";

// Section description renders inline beside the heading (the `kicker` slot),
// not as a `?` hover — `tooltip` is kept as an alias so existing callers work.
export function Section({ title, tooltip, kicker, children }) {
  return <DSSection label={title} kicker={kicker ?? tooltip}>{children}</DSSection>;
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
        if (await copyText(value)) notify({ message, variant: "success" });
        else notify({ message: "Copy failed", variant: "error" });
      }}
    >
      Copy
    </Button>
  );
}
