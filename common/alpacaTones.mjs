import { ALPACA_FOLD, BRAND_INK, foldFacets } from "./folds.mjs";
import { contrastRatio, creaseTones } from "./crease.mjs";

export const TONAL_MIN_SIZE = 48;
export const TONE_GROUNDS = { light: "#ffffff", dark: "#0c0b09" };

export const isTonalSize = (px) => px >= TONAL_MIN_SIZE;

export const alpacaTones = (mode) =>
  [...creaseTones(BRAND_INK[mode], TONE_GROUNDS[mode])].sort((a, b) => contrastRatio(b, "#000000") - contrastRatio(a, "#000000"));

export const tonalAlpacaPolygons = (mode) => {
  const tones = alpacaTones(mode);
  return foldFacets(ALPACA_FOLD).map(({ tone, points }) => ({ points, fill: tones[tone], tone }));
};
