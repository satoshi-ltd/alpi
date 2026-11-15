import { WG_ALPHA, WG_POP, WG_TURNS } from "../../../common/workgroupMark.mjs";

const rotation = ([ry, rx, rz]) => `rotateY(${ry}deg) rotateX(${rx}deg) rotateZ(${rz}deg)`;
const pct = (t) => `${Math.round(t * 1000) / 10}%`;
const keyframes = (prefix, name, seconds, frames) =>
  `.${prefix}-${name}{animation-name: ${prefix}-${name}; animation-duration: ${seconds}s}@keyframes ${prefix}-${name}{${frames}}`;
const at = (k, s) => `transform: translate(calc(var(--ox) * ${k}), calc(var(--oy) * ${k})) scale(${s})`;
const chase = WG_ALPHA.chase;

export const WG_CSS = [
  keyframes("am", "wg-fill", 2.4, `0%,100%{opacity: ${chase}}50%{opacity: 1}`),
  keyframes("am", "wg-chase", 2.4, `0%,46%,100%{opacity: ${chase}}12%,30%{opacity: 1}`),
  keyframes("am", "wg-pop", 2.8, `0%,6%,60%,100%{${at(1, WG_POP[1])}}14%{${at(0.4, 0.95)}}24%{${at(1.6, 1.12)}}33%{${at(0.9, 1.02)}}40%{${at(1.15, 1.07)}}47%{${at(1, WG_POP[1])}}`),
  keyframes("am", "wg-shiver", 5.6, "0%,14%,100%{transform: none}2%,6%,10%{transform: translate(-1.4px, 0)}4%,8%,12%{transform: translate(1.4px, 0)}"),
  ...Object.entries(WG_TURNS).map(([key, { dur, frames }]) =>
    keyframes("vt", `wg-${key}`, dur, frames.map(([t, ...pose]) => `${pct(t)}{transform: ${rotation(pose)}}`).join(""))),
].join("");
