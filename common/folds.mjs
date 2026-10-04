import { ALPI_LOWRES_PATHS, ALPI_PATHS } from "./alpiMark.mjs";

export const LIGHT = 0;
export const BASE = 1;
export const SHADE = 2;
export const MAX_FACETS = 6;
export const MIN_ASPECT = 0.8;
export const WORKGROUP_FOLD = "honeycomb";
export const ALPACA_FOLD = "alpaca";
export const ALPACA_LOW_FOLD = "alpaca-low";

const polar = (cx, cy, r, deg) => [cx + r * Math.cos((deg * Math.PI) / 180), cy + r * Math.sin((deg * Math.PI) / 180)];

const rotate = (points, deg, [cx, cy] = [50, 50]) => {
  const c = Math.cos((deg * Math.PI) / 180);
  const s = Math.sin((deg * Math.PI) / 180);
  return points.map(([x, y]) => [cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c]);
};

const hexagon = (cx, cy, r) => Array.from({ length: 6 }, (_, k) => polar(cx, cy, r, -90 + 60 * k));

const facet = (tone, ...points) => ({ tone, points });

const star = () => {
  const outer = Array.from({ length: 5 }, (_, k) => polar(50, 55, 48, -90 + k * 72));
  const inner = Array.from({ length: 5 }, (_, k) => polar(50, 55, 21, -54 + k * 72));
  const tones = [LIGHT, BASE, SHADE, SHADE, LIGHT];
  return outer.map((tip, k) => facet(tones[k], [50, 55], inner[(k + 4) % 5], tip, inner[k]));
};

const feather = () => {
  const base = [
    facet(LIGHT, [50, 4], [37, 22], [33, 48], [40, 70], [50, 78]),
    facet(BASE, [50, 4], [64, 16], [71, 38], [50, 45]),
    facet(SHADE, [50, 45], [64, 45], [70, 58], [64, 72], [50, 80]),
    facet(SHADE, [48, 80], [52, 80], [52, 99], [48, 99]),
  ];
  return base.map(({ tone, points }) => ({ tone, points: rotate(points, 42) }));
};

const honeycomb = () => {
  const r = 28;
  const step = r * 1.732;
  return [
    facet(LIGHT, ...hexagon(50, r, r)),
    facet(BASE, ...hexagon(50 - step / 2, r + step * 0.866, r)),
    facet(SHADE, ...hexagon(50 + step / 2, r + step * 0.866, r)),
  ];
};

export const FOLDS = {
  diamond: () => [
    facet(LIGHT, [50, 2], [2, 50], [50, 50]),
    facet(BASE, [50, 2], [98, 50], [50, 50]),
    facet(BASE, [2, 50], [50, 98], [50, 50]),
    facet(SHADE, [98, 50], [50, 98], [50, 50]),
  ],
  house: () => [
    facet(LIGHT, [50, 6], [2, 50], [50, 50]),
    facet(BASE, [50, 6], [98, 50], [50, 50]),
    facet(BASE, [14, 50], [50, 50], [50, 94], [14, 94]),
    facet(SHADE, [50, 50], [86, 50], [86, 94], [50, 94]),
  ],
  heart: () => [
    facet(LIGHT, [50, 30], [30, 8], [4, 28], [50, 56]),
    facet(BASE, [4, 28], [14, 60], [50, 94], [50, 56]),
    facet(BASE, [50, 30], [70, 8], [96, 28], [50, 56]),
    facet(SHADE, [96, 28], [86, 60], [50, 94], [50, 56]),
  ],
  plane: () => [
    facet(LIGHT, [97, 5], [5, 44], [44, 60]),
    facet(BASE, [97, 5], [44, 60], [58, 95]),
    facet(SHADE, [44, 60], [58, 95], [36, 76]),
  ],
  shield: () => [
    facet(LIGHT, [50, 4], [8, 18], [10, 50], [50, 50]),
    facet(BASE, [10, 50], [50, 50], [50, 96]),
    facet(BASE, [50, 4], [92, 18], [90, 50], [50, 50]),
    facet(SHADE, [90, 50], [50, 50], [50, 96]),
  ],
  rocket: () => [
    facet(LIGHT, [50, 4], [30, 36], [70, 36]),
    facet(LIGHT, [30, 36], [50, 36], [50, 80], [30, 80]),
    facet(BASE, [50, 36], [70, 36], [70, 80], [50, 80]),
    facet(SHADE, [30, 52], [30, 86], [6, 94]),
    facet(SHADE, [70, 52], [94, 94], [70, 86]),
    facet(SHADE, [38, 80], [62, 80], [56, 96], [44, 96]),
  ],
  star,
  tree: () => [
    facet(LIGHT, [50, 4], [30, 30], [70, 30]),
    facet(BASE, [30, 30], [70, 30], [82, 58], [18, 58]),
    facet(SHADE, [18, 58], [82, 58], [94, 86], [6, 86]),
    facet(SHADE, [44, 86], [56, 86], [56, 98], [44, 98]),
  ],
  box: () => [
    facet(LIGHT, [6, 6], [94, 6], [70, 30], [30, 30]),
    facet(LIGHT, [6, 6], [30, 30], [30, 70], [6, 94]),
    facet(BASE, [94, 6], [94, 94], [70, 70], [70, 30]),
    facet(BASE, [6, 94], [30, 70], [70, 70], [94, 94]),
    facet(SHADE, [30, 30], [70, 30], [70, 70], [30, 70]),
  ],
  crown: () => [
    facet(LIGHT, [6, 18], [28, 56], [30, 94], [16, 94]),
    facet(BASE, [28, 56], [50, 4], [50, 94], [30, 94]),
    facet(SHADE, [50, 4], [72, 56], [70, 94], [50, 94]),
    facet(BASE, [72, 56], [94, 18], [84, 94], [70, 94]),
  ],
  feather,
  bulb: () => [
    facet(LIGHT, [50, 4], [26, 12], [10, 32], [12, 52], [26, 64], [36, 74], [50, 74]),
    facet(BASE, [50, 4], [74, 12], [90, 32], [88, 52], [74, 64], [64, 74], [50, 74]),
    facet(SHADE, [36, 74], [64, 74], [64, 86], [36, 86]),
    facet(BASE, [40, 86], [60, 86], [55, 99], [45, 99]),
  ],
  [WORKGROUP_FOLD]: honeycomb,
};

export const FOLD_IDS = Object.keys(FOLDS).filter((id) => id !== WORKGROUP_FOLD);

export const FOLD_MODELS = {
  diamond: "kite base", house: "house", heart: "heart", plane: "dart", shield: "shield", rocket: "rocket", star: "lucky star",
  tree: "pine tree", box: "masu box", crown: "paper crown", feather: "feather", bulb: "light bulb", honeycomb: "hexagon honeycomb",
};

const ALPACA_TONES = [BASE, SHADE, LIGHT, SHADE, SHADE, BASE, LIGHT, BASE, SHADE, LIGHT, LIGHT, BASE];
const alpaca = () =>
  ALPI_PATHS.map((d, i) =>
    facet(ALPACA_TONES[i % ALPACA_TONES.length], ...[...d.matchAll(/(-?[\d.]+),(-?[\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])])),
  );

const LOW_TONES = [BASE, LIGHT, SHADE, SHADE, LIGHT, BASE, LIGHT, SHADE, BASE];
const alpacaLow = () =>
  ALPI_LOWRES_PATHS.map((d, i) =>
    facet(LOW_TONES[i], ...[...d.matchAll(/(-?[\d.]+),(-?[\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])])),
  );

const DRAWN = { ...FOLDS, [ALPACA_FOLD]: alpaca, [ALPACA_LOW_FOLD]: alpacaLow };
const RENDERABLE = [...FOLD_IDS, WORKGROUP_FOLD, ALPACA_FOLD];

export const DEFAULT_FOLD = "diamond";
export const FOLD_SIZES = { row: 16, header: 20, hero: 72 };
export const ALPACA_ROW_SCALE = 1.3;
export const isLegacyFold = (value) => normaliseFold(value) === DEFAULT_FOLD;
export const isHexColour = (value) => /^#[0-9a-f]{6}$/i.test(value ?? "");
export const FALLBACK_ACCENT = "#f0b447";

export const normaliseFold = (value) => {
  const id = typeof value === "string" ? value.trim().toLowerCase() : "";
  return RENDERABLE.includes(id) ? id : DEFAULT_FOLD;
};

export function foldFacets(id) {
  const facets = DRAWN[id]();
  const points = facets.flatMap((f) => f.points);
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const k = 94 / Math.max(x1 - x0, y1 - y0);
  const [cx, cy] = [(x0 + x1) / 2, (y0 + y1) / 2];
  return facets.map(({ tone, points: pts }) => ({ tone, points: pts.map(([x, y]) => [50 + (x - cx) * k, 50 + (y - cy) * k]) }));
}

export function insetPolygon(points, d) {
  const n = points.length;
  const area = points.reduce((sum, [x, y], i) => sum + x * points[(i + 1) % n][1] - points[(i + 1) % n][0] * y, 0);
  const sign = area > 0 ? 1 : -1;
  const lines = points.map(([x1, y1], i) => {
    const [x2, y2] = points[(i + 1) % n];
    const [dx, dy] = [x2 - x1, y2 - y1];
    const length = Math.hypot(dx, dy) || 1;
    return [x1 + (-dy / length) * sign * d, y1 + (dx / length) * sign * d, dx, dy];
  });
  return points.map((point, i) => {
    const [px, py, ax, ay] = lines[(i + n - 1) % n];
    const [qx, qy, bx, by] = lines[i];
    const det = ax * by - ay * bx;
    if (Math.abs(det) < 1e-9) return point;
    const t = ((qx - px) * by - (qy - py) * bx) / det;
    let [x, y] = [px + ax * t, py + ay * t];
    const [vx, vy] = [x - point[0], y - point[1]];
    const reach = Math.hypot(vx, vy);
    if (reach > 3 * d) [x, y] = [point[0] + (vx * 3 * d) / reach, point[1] + (vy * 3 * d) / reach];
    return [x, y];
  });
}

const lin = (v) => (v / 255 <= 0.04045 ? v / 255 / 12.92 : ((v / 255 + 0.055) / 1.055) ** 2.4);
const gamma = (v) => {
  const c = Math.max(0, Math.min(1, v));
  return c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055;
};
const channels = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));

export function toOklab(hex) {
  const [r, g, b] = channels(hex).map(lin);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

function fromOklch(L, C, h) {
  for (let chroma = C; chroma > 0; chroma -= 0.004) {
    const a = chroma * Math.cos((h * Math.PI) / 180);
    const b = chroma * Math.sin((h * Math.PI) / 180);
    const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
    const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
    const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
    const rgb = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
    if (rgb.every((v) => v >= -1e-4 && v <= 1 + 1e-4)) return "#" + rgb.map((v) => Math.round(gamma(v) * 255).toString(16).padStart(2, "0")).join("");
  }
  const grey = Math.round(gamma(L ** 3) * 255).toString(16).padStart(2, "0");
  return `#${grey}${grey}${grey}`;
}

const asSixDigits = (value) => {
  const text = typeof value === "string" ? value.trim().toLowerCase() : "";
  if (/^#[0-9a-f]{6}$/.test(text)) return text;
  return /^#[0-9a-f]{3}$/.test(text) ? "#" + [...text.slice(1)].map((c) => c + c).join("") : FALLBACK_ACCENT;
};

export const INK_TONES = {
  "#14110c": ["#14110c", "#14110c", "#14110c"],
  "#f3efe6": ["#f3efe6", "#f3efe6", "#f3efe6"],
  "#7a7468": ["#7a7468", "#7a7468", "#7a7468"],
};

export const INK_CREASE = {
  light: ["#14110c", "#4f4a41", "#8a8578"],
  dark: ["#ffffff", "#d9d4c7", "#a09a8c"],
};

export function foldTones(value) {
  const accent = asSixDigits(value);
  if (INK_TONES[accent]) return INK_TONES[accent];
  const [L, a, b] = toOklab(accent);
  const C = Math.hypot(a, b);
  const h = ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360;
  return [fromOklch(Math.min(L + 0.11, 0.97), C * 0.82, h), accent, fromOklch(Math.max(L - 0.15, 0.05), C * 0.95, h)];
}

export function foldPolygons(id, accent, size = 64) {
  const tones = foldTones(accent);
  const gap = id === ALPACA_FOLD || id === ALPACA_LOW_FOLD ? 0 : Math.max(1.1, 30 / size);
  return foldFacets(id).map(({ tone, points }) => ({ points: gap ? insetPolygon(points, gap) : points, fill: tones[tone], tone }));
}

export function shiftLightness(value, delta) {
  const accent = asSixDigits(value);
  const [L, a, b] = toOklab(accent);
  const C = Math.hypot(a, b);
  const h = ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360;
  return fromOklch(Math.min(0.98, Math.max(0.04, L + delta)), C * (delta > 0 ? 0.85 : 0.95), h);
}

export const BRAND_INK = { light: "#14110c", dark: "#f3efe6" };

export const defaultAsAlpaca = (accent = null) => (profile) =>
  profile && (profile.is_default || profile.name === "default") ? { ...profile, fold: ALPACA_FOLD, accent } : profile;

export const withDefaultAlpaca = defaultAsAlpaca();
