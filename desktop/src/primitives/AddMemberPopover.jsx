import Popover from "./Popover.jsx";
import { Diamond, Mono, Eyebrow } from "./index.js";
import styles from "./AddMemberPopover.module.css";

export default function AddMemberPopover({
  open,
  onClose,
  candidates = [],   // [{ id, accent, pubkey }]
  onPick,
}) {
  return (
    <Popover open={open} onClose={onClose} width="var(--pop-md)">
      <div className={styles.head}>
        <Eyebrow>Add member</Eyebrow>
      </div>
      <div className={`col ${styles.list}`}>
        {candidates.length === 0 && (
          <div className={styles.empty}>No more peers to add</div>
        )}
        {candidates.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => {
              onPick?.(c);
              onClose?.();
            }}
            className={`row row-gap ${styles.item}`}
          >
            <Diamond color={c.accent} />
            <Mono className={styles.label}>@{c.id}</Mono>
            <Mono className={styles.suffix}>
              …{(c.pubkey || "").slice(-7)}
            </Mono>
          </button>
        ))}
      </div>
    </Popover>
  );
}
