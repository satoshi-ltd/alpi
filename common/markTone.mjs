import { contrastRatio, luminance } from "./name.mjs";
import { isHexColour, shiftLightness } from "./shapes.mjs";
import { palettes } from "./tokens.mjs";

export const MARK_EYE_FLOOR = 3;
export const MARK_STEP = 0.01;

export function toneAgainst(accent, ground, floor) {
  const direction = luminance(ground) > 0.2 ? -1 : 1;
  let [delta, tone] = [0, accent];
  while (contrastRatio(tone, ground) < floor && delta < 1) {
    delta = Number((delta + MARK_STEP).toFixed(2));
    tone = shiftLightness(accent, direction * delta);
  }
  return tone;
}

const lightTones = new Map();

export function markTone(accent, theme) {
  if (theme !== "light" || !isHexColour(accent)) return accent;
  const hex = accent.toLowerCase();
  if (!lightTones.has(hex)) lightTones.set(hex, toneAgainst(hex, palettes.light.markEye, MARK_EYE_FLOOR));
  const tone = lightTones.get(hex);
  return tone === hex ? accent : tone;
}

export function markTones(accent) {
  const light = markTone(accent, "light");
  return light === accent ? null : { light, dark: accent };
}
