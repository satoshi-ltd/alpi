import { useMemo } from "react";
import { creaseGradient, creaseTones } from "../../../common/crease.mjs";
import { palettes } from "../../../common/tokens.mjs";
import styles from "./Crease.module.css";

const LIGHT_VARS = ["--crease-l1", "--crease-l2", "--crease-l3"];
const DARK_VARS = ["--crease-d1", "--crease-d2", "--crease-d3"];

export function creaseVars(accent) {
  const light = creaseTones(accent, palettes.light.bgPane);
  const dark = creaseTones(accent, palettes.dark.bgPane);
  const vars = {
    "--crease-light": creaseGradient(light),
    "--crease-dark": creaseGradient(dark),
  };
  light.forEach((hex, i) => {
    vars[LIGHT_VARS[i]] = hex;
  });
  dark.forEach((hex, i) => {
    vars[DARK_VARS[i]] = hex;
  });
  return vars;
}

export const creaseInk = styles.ink;

export default function Crease({ text, accent, as: Tag = "span", className = "", size, style }) {
  const vars = useMemo(() => creaseVars(accent), [accent]);
  const merged = size ? { ...vars, fontSize: size, ...style } : { ...vars, ...style };
  return (
    <Tag className={`${styles.crease} ${className}`.trim()} style={merged}>
      {text}
    </Tag>
  );
}
