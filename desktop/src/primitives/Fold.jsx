import { useMemo } from "react";
import { ALPACA_FOLD, alpacaDrawnSize, BRAND_INK, FOLD_SIZES, foldPolygons, isHexColour, normaliseFold } from "../../../common/folds.mjs";
import { alpacaTones, isTonalSize } from "../../../common/alpacaTones.mjs";
import styles from "./Fold.module.css";

const BASE = "var(--c, var(--ink-3))";
const RIPPLE_SECONDS = 1.4;
export const ALPACA_VARS = { "--alp-l": BRAND_INK.light, "--alp-d": BRAND_INK.dark };
const [LT0, LT1, LT2] = alpacaTones("light");
const [DT0, DT1, DT2] = alpacaTones("dark");
const TONAL_VARS = { "--alp-l0": LT0, "--alp-l1": LT1, "--alp-l2": LT2, "--alp-d0": DT0, "--alp-d1": DT1, "--alp-d2": DT2 };
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
  const drawn = alpaca && !specimen ? alpacaDrawnSize(px) : px;
  const tonal = alpaca && !unfolded && !outlined && isTonalSize(drawn);
  const slot = [styles.slot, alpaca ? styles.alpaca : "", className].filter(Boolean).join(" ");
  return (
    <span className={slot} style={{ width: px, height: px, "--c": color || undefined, ...(alpaca ? ALPACA_VARS : {}), ...(tonal ? TONAL_VARS : {}), ...style }} aria-hidden data-fold={id} data-unfolded={unfolded ? "" : undefined}>
      <svg
        viewBox="0 0 100 100"
        width={drawn}
        height={drawn}
        style={{ display: "block", overflow: "visible", flexShrink: 0 }}
      >
        {polygons.map(({ points, fill, tone }, i) => {
          const paint = alpaca ? (tonal ? `var(--alp-t${tone})` : "var(--alp)") : hex ? fill : TONES[tone];
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
