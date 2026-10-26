import { createElement } from "react";
import { ICONS, ICON_ALIASES } from "../../../common/iconPaths.mjs";
import { iconSizesAllowed, iconStrokeRendered } from "../../../common/tokens.mjs";
import styles from "./Icon.module.css";

const [SM, MD] = iconSizesAllowed.desktop;
const SIZES = { sm: SM, md: MD };

export const iconPx = (size) => (typeof size === "number" ? (size <= SM ? SM : MD) : SIZES[size] ?? MD);
export const iconStroke = (px, viewBox) => (iconStrokeRendered * viewBox) / px;

export default function Icon({
  name,
  size = "md",
  color = null,
  className = "",
  style = null,
  ...rest
}) {
  const def = ICONS[ICON_ALIASES[name] ?? name];
  if (!def) {
    if (typeof console !== "undefined") console.warn(`<Icon name="${name}"/> not in map`);
    return null;
  }
  const els = Array.isArray(def) ? def : def.els;
  const vb = (!Array.isArray(def) && def.vb) || "0 0 24 24";
  const filled = !Array.isArray(def) && def.sw === 0;
  const fill = (!Array.isArray(def) && def.fill) || "none";
  const px = iconPx(size);
  const sw = iconStroke(px, Number(vb.split(" ")[2]));
  return (
    <svg
      {...rest}
      viewBox={vb}
      width={px}
      height={px}
      fill={fill}
      stroke={filled ? "none" : "currentColor"}
      strokeWidth={filled ? undefined : sw}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`${styles.icon} ds-icon ${className}`.trim()}
      style={{ color: color ?? undefined, ...style }}
      aria-hidden="true"
      data-icon={name}
    >
      {els.map(([tag, attrs], i) => createElement(tag, { key: i, ...attrs }))}
    </svg>
  );
}
