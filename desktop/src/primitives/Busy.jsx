import { TWIN } from "../lib/brandMark.js";
import { BUSY_LABEL, BUSY_MIN_MARK_PX } from "../../../common/busy.mjs";
import { useBusyVisible } from "../lib/useBusyVisible.js";
import Fold from "./Fold.jsx";
import styles from "./Busy.module.css";

export default function Busy({ active = true, ...mark }) {
  return useBusyVisible(active) ? <BusyMark {...mark} /> : null;
}

export function BusyMark({ label = null, size = null, className = "" }) {
  const px = Math.max(size ?? BUSY_MIN_MARK_PX, BUSY_MIN_MARK_PX);
  const root = [styles.busy, styles.inline, className].filter(Boolean).join(" ");
  return (
    <span className={root} role="status" aria-label={label || BUSY_LABEL}>
      <Fold shape={TWIN} size={px} state="busy" seed="alpi-busy" />
      {label ? <span className={styles.label}>{label}</span> : null}
    </span>
  );
}
