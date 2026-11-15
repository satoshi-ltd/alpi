import { shiftLightness } from "./shapes.mjs";

export const NAME_FONT = "Bricolage Grotesque";
export const NAME_MIN_CONTRAST = 4.5;
export const NAME_STEP = 0.12;
const NUDGE = 0.02;

const lin = (v) => (v / 255 <= 0.04045 ? v / 255 / 12.92 : ((v / 255 + 0.055) / 1.055) ** 2.4);
export const luminance = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => lin(parseInt(hex.slice(i, i + 2), 16)));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

export function contrastRatio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const sixDigits = (hex) => {
  if (typeof hex !== "string") return null;
  if (/^#[0-9a-f]{6}$/i.test(hex)) return hex.toLowerCase();
  return /^#[0-9a-f]{3}$/i.test(hex) ? `#${[...hex.slice(1)].map((c) => c + c).join("")}`.toLowerCase() : null;
};

export function nameTone(rawAccent, rawGround) {
  const accent = sixDigits(rawAccent);
  const ground = sixDigits(rawGround);
  if (!accent || !ground) return null;
  const direction = luminance(ground) > 0.2 ? -1 : 1;
  for (let delta = NAME_STEP; delta < 1; delta += NUDGE) {
    const tone = shiftLightness(accent, direction * delta);
    if (contrastRatio(tone, ground) >= NAME_MIN_CONTRAST) return tone;
  }
  return direction < 0 ? "#141414" : "#ffffff";
}
