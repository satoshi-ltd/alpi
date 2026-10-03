import { BRAND_INK, INK_CREASE, shiftLightness } from "./folds.mjs";

export const CREASE_FONT = "Bricolage Grotesque";
export const CREASE_MIN_CONTRAST = 3;
export const CREASE_ANGLE = 115;
export const CREASE_SLIT = 0.6;
export const CREASE_SLIT_CSS = "max(0.6px, 0.011em)";

const lin = (v) => (v / 255 <= 0.04045 ? v / 255 / 12.92 : ((v / 255 + 0.055) / 1.055) ** 2.4);
const luminance = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => lin(parseInt(hex.slice(i, i + 2), 16)));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

export function contrastRatio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TIGHT_STEP = 0.07;
const LADDER = [0, 0.11, -0.15, 0.2, -0.28, -0.4, -0.5, 0.28];

export function creaseTones(accent, ground) {
  const onLight = luminance(ground) > 0.2;
  if (!/^#[0-9a-f]{6}$/i.test(accent ?? "") || [BRAND_INK.light, BRAND_INK.dark].includes(accent.toLowerCase())) return INK_CREASE[onLight ? "light" : "dark"];
  const base = accent.toLowerCase();
  const candidates = LADDER.map((delta) => (delta === 0 ? base : shiftLightness(base, delta)));
  const passing = candidates.filter((hex, i) => candidates.indexOf(hex) === i && contrastRatio(hex, ground) >= CREASE_MIN_CONTRAST);
  if (passing.length >= 3 && luminance(ground) > 0.2 && passing[0] !== base) {
    return [passing[0], shiftLightness(passing[0], -TIGHT_STEP), shiftLightness(passing[0], -2 * TIGHT_STEP)];
  }
  if (passing.length >= 3) return passing.slice(0, 3);
  const darkGround = luminance(ground) < 0.2;
  const fallback = darkGround ? ["#ffffff", "#ededed", "#b4b4b4"] : ["#141414", "#454545", "#2a2a2a"];
  return [...passing, ...fallback].slice(0, 3);
}

export function creaseGradient(tones, slit = CREASE_SLIT_CSS) {
  const [a, b, c] = tones;
  const s = typeof slit === "number" ? `${slit}px` : slit;
  return `linear-gradient(${CREASE_ANGLE}deg, ${a} 0 calc(33% - ${s}), transparent calc(33% - ${s}) calc(33% + ${s}), ${b} calc(33% + ${s}) calc(66% - ${s}), transparent calc(66% - ${s}) calc(66% + ${s}), ${c} calc(66% + ${s}) 100%)`;
}
