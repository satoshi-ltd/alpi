import { Diamond, Mono, ChevDownIcon } from "./index.js";
import styles from "./ToPickerBar.module.css";

export default function ToPickerBar({ profile, model, onClick, open }) {
  const accent = profile?.accent || "var(--ink-3)";
  return (
    <button
      type="button"
      className={styles.bar}
      onClick={onClick}
      aria-expanded={open || undefined}
    >
      <span className={`eyebrow ${styles.label}`}>To</span>
      <Diamond color={accent} />
      <Mono className={styles.handle}>@{profile?.name ?? "—"}</Mono>
      {model && (
        <>
          <span className={styles.sep}>·</span>
          <Mono className={styles.model}>{model}</Mono>
        </>
      )}
      <span className={styles.spacer} />
      <ChevDownIcon style={{ width: 14, height: 14, color: "var(--ink-3)" }} />
    </button>
  );
}
