import { useMemo } from "react";
import { ALPACA_FOLD, ALPACA_ROW_SCALE, BRAND_INK, FOLD_SIZES, foldPolygons, isHexColour, normaliseFold } from "../../../common/folds.mjs";
import styles from "./Fold.module.css";

const BASE = "var(--c, var(--ink-3))";
const RIPPLE_SECONDS = 1.4;
export const ALPACA_VARS = { "--alp-l": BRAND_INK.light, "--alp-d": BRAND_INK.dark };
const TONES = [`color-mix(in srgb, ${BASE} 62%, white)`, BASE, `color-mix(in srgb, ${BASE} 72%, black)`];

export default function Fold({ fold, color: given, size, pulse = false, outlined = false, unfolded = false, className = "", style }) {
  const specimen = typeof size === "number";
  const px = specimen ? size : size === "md" ? FOLD_SIZES.header : FOLD_SIZES.row;
  const id = normaliseFold(fold);
  const alpaca = id === ALPACA_FOLD;
  const color = alpaca ? "var(--accent)" : given;
  const hex = isHexColour(color);
  const polygons = useMemo(() => foldPolygons(id, hex ? color : "#808080", px), [id, color, hex, px]);
  const rippling = pulse && !unfolded;
  const drawn = alpaca && !specimen ? px * ALPACA_ROW_SCALE : px;
  const slot = [styles.slot, alpaca ? styles.alpaca : "", className].filter(Boolean).join(" ");
  return (
    <span className={slot} style={{ width: px, height: px, "--c": color || undefined, ...(alpaca ? ALPACA_VARS : {}), ...style }} aria-hidden data-fold={id} data-unfolded={unfolded ? "" : undefined}>
      <svg
        viewBox="0 0 100 100"
        width={drawn}
        height={drawn}
        style={{ display: "block", overflow: "visible", flexShrink: 0 }}
      >
        {polygons.map(({ points, fill, tone }, i) => {
          const paint = alpaca ? "var(--alp)" : hex ? fill : TONES[tone];
          const outline = unfolded
            ? { fill: "none", stroke: "var(--ink-3)", strokeWidth: 1, strokeDasharray: "2 1.5", strokeLinejoin: "round", vectorEffect: "non-scaling-stroke" }
            : outlined ? { fill: paint, fillOpacity: 0.22, stroke: paint, strokeWidth: 3, strokeLinejoin: "round" } : { fill: paint };
          const ripple = rippling ? { className: styles.cell, style: { animationDelay: `${(-(i / polygons.length) * RIPPLE_SECONDS).toFixed(2)}s` } } : {};
          return <polygon key={i} points={points.map((p) => p.map((v) => v.toFixed(2)).join(",")).join(" ")} {...outline} {...ripple} />;
        })}
      </svg>
    </span>
  );
}
