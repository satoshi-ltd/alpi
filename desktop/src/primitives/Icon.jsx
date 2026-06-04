import { createElement } from "react";
import { ICONS, ICON_ALIASES } from "./iconPaths.js";
import styles from "./Icon.module.css";

const SIZES = { xs: 9, sm: 12, md: 14, lg: 18, xl: 24 };

export default function Icon({
  name,
  size = "md",
  color = null,
  className = "",
  style = null,
  strokeWidth = null,
  ...rest
}) {
  const def = ICONS[ICON_ALIASES[name] ?? name];
  if (!def) {
    if (typeof console !== "undefined") console.warn(`<Icon name="${name}"/> not in map`);
    return null;
  }
  const els = Array.isArray(def) ? def : def.els;
  const vb = (!Array.isArray(def) && def.vb) || "0 0 24 24";
  const sw = strokeWidth != null ? strokeWidth : !Array.isArray(def) && def.sw != null ? def.sw : 2;
  const fill = (!Array.isArray(def) && def.fill) || "none";
  const px = typeof size === "number" ? size : SIZES[size] || SIZES.md;
  return (
    <svg
      viewBox={vb}
      width={px}
      height={px}
      fill={fill}
      stroke={sw === 0 ? "none" : "currentColor"}
      strokeWidth={sw || undefined}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`${styles.icon} ds-icon ${className}`.trim()}
      style={{ color: color ?? undefined, ...style }}
      aria-hidden="true"
      {...rest}
    >
      {els.map(([tag, attrs], i) => createElement(tag, { key: i, ...attrs }))}
    </svg>
  );
}
