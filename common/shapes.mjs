import { SHAPE_ORDER } from "./agentMarks.mjs";

export const SHAPE_IDS = [...SHAPE_ORDER];
export const DEFAULT_SHAPE = "round";
export const TWIN_SHAPE = "twin";
export const WORKGROUP_SHAPE = "honeycomb";
const NAMED = new Set([...SHAPE_IDS, TWIN_SHAPE, WORKGROUP_SHAPE]);

export const isHexColour = (value) => /^#[0-9a-f]{6}$/i.test(value ?? "");
export const FALLBACK_ACCENT = "#f0b447";

export const shapeOf = (value) => {
  const id = typeof value === "string" ? value.trim().toLowerCase() : "";
  return NAMED.has(id) ? id : DEFAULT_SHAPE;
};

export const profileShape = (profile) => shapeOf(profile?.shape);

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

export function shiftLightness(value, delta) {
  const accent = asSixDigits(value);
  const [L, a, b] = toOklab(accent);
  const C = Math.hypot(a, b);
  const h = ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360;
  return fromOklch(Math.min(0.98, Math.max(0.04, L + delta)), C * (delta > 0 ? 0.85 : 0.95), h);
}

export const BRAND_INK = { light: "#14110c", dark: "#f3efe6" };

export const defaultAsTwin = (accent = null) => (profile) => {
  if (!profile) return profile;
  return profile.is_default || profile.name === "default" ? { ...profile, shape: TWIN_SHAPE, accent } : profile;
};
