import { fontSizes } from './tokens';

export const DEFAULT_TEXT_SCALE = 1;

// Four steps, not desktop's nine: RN multiplies these again by the OS font scale, so the usable headroom is narrower than a webview zoom's.
export const TEXT_SCALES = [
  { value: 0.9, label: 'Small' },
  { value: 1, label: 'Default' },
  { value: 1.15, label: 'Large' },
  { value: 1.3, label: 'Largest' },
];

const VALUES = TEXT_SCALES.map((step) => step.value);

export const MIN_TEXT_SCALE = VALUES[0];
export const MAX_TEXT_SCALE = VALUES[VALUES.length - 1];

function parse(value) {
  if (typeof value === 'number') return value;
  if (typeof value === 'string' && value.trim() !== '') return Number(value);
  return NaN;
}

export function clampTextScale(value) {
  const v = parse(value);
  if (!Number.isFinite(v)) return DEFAULT_TEXT_SCALE;
  if (v <= MIN_TEXT_SCALE) return MIN_TEXT_SCALE;
  if (v >= MAX_TEXT_SCALE) return MAX_TEXT_SCALE;
  return VALUES.reduce((best, step) =>
    Math.abs(step - v) < Math.abs(best - v) ? step : best,
  );
}

export function stepTextScale(current, direction) {
  if (!direction) return DEFAULT_TEXT_SCALE;
  const index = VALUES.indexOf(clampTextScale(current));
  const next = index + (direction > 0 ? 1 : -1);
  return VALUES[Math.min(VALUES.length - 1, Math.max(0, next))];
}

export function textScaleLabel(value) {
  const scale = clampTextScale(value);
  return TEXT_SCALES.find((step) => step.value === scale).label;
}

export function scaleFontSizes(value) {
  const scale = clampTextScale(value);
  const scaled = {};
  for (const [key, size] of Object.entries(fontSizes)) scaled[key] = Math.round(size * scale);
  return scaled;
}
