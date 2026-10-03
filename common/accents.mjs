import { normaliseFold, toOklab } from "./folds.mjs";

export const ACCENTS = [
  ["amber", "#f0b447"],
  ["orange", "#f28832"],
  ["vermilion", "#f05940"],
  ["rose", "#f36a8a"],
  ["magenta", "#df4b9d"],
  ["violet", "#9b5ad9"],
  ["indigo", "#6572e4"],
  ["blue", "#3899e2"],
  ["sky", "#3ac9f3"],
  ["teal", "#2cb3b5"],
  ["green", "#3ec173"],
  ["lime", "#9fc93e"],
];

export const ACCENT_HEXES = ACCENTS.map(([, hex]) => hex);

export const ACCENT_FOLDS = {
  amber: "diamond", vermilion: "house", rose: "heart", magenta: "plane", blue: "shield", teal: "rocket",
  violet: "star", green: "tree", sky: "box", indigo: "crown", lime: "feather", orange: "bulb",
};

const GREY_CHROMA = 0.04;
export const LEGACY_ACCENTS = { "#7e8792": "#3ac9f3" };

export function nearestAccent(hex) {
  if (!/^#[0-9a-f]{6}$/i.test(hex ?? "")) return null;
  const legacy = LEGACY_ACCENTS[hex.toLowerCase()];
  if (legacy) return ACCENTS.find(([, candidate]) => candidate === legacy);
  const [L, a, b] = toOklab(hex.toLowerCase());
  if (Math.hypot(a, b) < GREY_CHROMA) return null;
  const hueGap = (x, y) => Math.abs(Math.atan2(Math.sin(Math.atan2(x[2], x[1]) - Math.atan2(y[2], y[1])), Math.cos(Math.atan2(x[2], x[1]) - Math.atan2(y[2], y[1]))));
  let best = null;
  let bestDistance = Infinity;
  for (const [name, candidate] of ACCENTS) {
    const target = toOklab(candidate);
    const distance = 4 * hueGap([L, a, b], target) ** 2 + 0.25 * (L - target[0]) ** 2;
    if (distance < bestDistance) [best, bestDistance] = [[name, candidate], distance];
  }
  return best;
}

export function selectedAccent(hex) {
  const exact = ACCENT_HEXES.find((candidate) => candidate === String(hex ?? "").toLowerCase());
  return exact ?? nearestAccent(hex)?.[1] ?? null;
}

export function accentName(hex) {
  const swatch = selectedAccent(hex);
  return ACCENTS.find(([, candidate]) => candidate === swatch)?.[0] ?? null;
}

export function pairName(fold, hex) {
  const colour = accentName(hex);
  const id = normaliseFold(fold);
  return colour ? `${colour} ${id}` : id;
}
