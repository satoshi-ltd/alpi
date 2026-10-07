import { useMemo } from "react";
import { ALPACA_FOLD, foldPolygons } from "../../../common/folds.mjs";
import { BUSY_DIM, BUSY_LABEL, BUSY_MIN_MARK_PX, BUSY_WAVE_S, busyFacetDelays } from "../../../common/busy.mjs";
import { useBusyVisible, useReducedMotion } from "../lib/useBusyVisible.js";
import { ALPACA_VARS } from "./Fold.jsx";
import foldStyles from "./Fold.module.css";
import styles from "./Busy.module.css";

export const BUSY_PAGE_PX = 56;

export default function Busy({ active = true, ...mark }) {
  return useBusyVisible(active) ? <BusyMark {...mark} /> : null;
}

export function BusyMark({ label = null, page = false, size = null, className = "" }) {
  const still = useReducedMotion();
  const px = Math.max(size ?? (page ? BUSY_PAGE_PX : BUSY_MIN_MARK_PX), BUSY_MIN_MARK_PX);
  const polygons = useMemo(() => foldPolygons(ALPACA_FOLD, "#808080", px), [px]);
  const delays = useMemo(() => busyFacetDelays(polygons.length), [polygons.length]);
  const root = [styles.busy, page ? styles.page : styles.inline, className].filter(Boolean).join(" ");
  return (
    <span className={root} role="status" aria-label={label || BUSY_LABEL} data-still={still ? "" : undefined}>
      <span className={`${styles.mark} ${foldStyles.alpaca}`} style={{ width: px, height: px, "--busy-dim": BUSY_DIM, ...ALPACA_VARS }} aria-hidden data-fold={ALPACA_FOLD}>
        <svg viewBox="0 0 100 100" width={px} height={px} className={styles.svg}>
          {polygons.map(({ points }, i) => (
            <polygon
              key={i}
              points={points.map((p) => p.map((v) => v.toFixed(2)).join(",")).join(" ")}
              fill="var(--alp)"
              className={still ? undefined : styles.facet}
              style={still ? undefined : { animationDuration: `${BUSY_WAVE_S}s`, animationDelay: `${delays[i]}s` }}
            />
          ))}
        </svg>
      </span>
      {label ? <span className={styles.label}>{label}</span> : null}
    </span>
  );
}
