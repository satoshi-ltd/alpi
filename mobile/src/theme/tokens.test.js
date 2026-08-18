import { describe, expect, it } from 'vitest';

import { profileAccents } from './accents';
import { palettes } from './tokens';

const MODES = ['light', 'dark'];

const CONSUMED_KEYS = [
  'accent',
  'bg',
  'bgElev',
  'bgInput',
  'bgPane',
  'bgSide',
  'danger',
  'hover',
  'ink',
  'ink2',
  'ink3',
  'ink4',
  'line',
  'line2',
  'selected',
  'success',
  'warning',
];

const srgb = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);

const channels = (hex) => {
  const v = hex.replace('#', '');
  return [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16));
};

const luminance = (hex) => {
  const [r, g, b] = channels(hex).map((c) => srgb(c / 255));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

describe('palettes', () => {
  it('exposes the same key set in every mode', () => {
    const [light, dark] = MODES.map((mode) => Object.keys(palettes[mode]).sort());
    expect(light).toEqual(dark);
  });

  it.each(MODES)('defines every consumed key in %s', (mode) => {
    const missing = CONSUMED_KEYS.filter((key) => !palettes[mode][key]);
    expect(missing).toEqual([]);
  });

  it.each(MODES)('resolves every key to a non-empty string in %s', (mode) => {
    const entries = Object.entries(palettes[mode]);
    expect(entries.length).toBeGreaterThan(0);
    for (const [key, value] of entries) {
      expect(typeof value, key).toBe('string');
      expect(value.length, key).toBeGreaterThan(0);
    }
  });
});

describe('accent', () => {
  it.each(MODES)('is defined in %s', (mode) => {
    expect(palettes[mode].accent).toMatch(/^#[0-9a-f]{6}$/);
  });

  it('keeps the dark accent tied to the alpi brand gold', () => {
    expect(palettes.dark.accent).toBe(profileAccents.alpi);
  });

  it.each(MODES)('clears 3:1 against the %s ground', (mode) => {
    expect(contrast(palettes[mode].accent, palettes[mode].bg)).toBeGreaterThanOrEqual(3);
  });

  it.each(MODES)('clears 3:1 against the %s SyncBar track', (mode) => {
    const ink = mode === 'light' ? '#0b1117' : '#e6edf3';
    const opacity = mode === 'light' ? 0.07 : 0.08;
    const bg = channels(palettes[mode].bg);
    const track = channels(ink)
      .map((c, i) => Math.round(c * opacity + bg[i] * (1 - opacity)))
      .reduce((hex, c) => hex + c.toString(16).padStart(2, '0'), '#');
    expect(contrast(palettes[mode].accent, track)).toBeGreaterThanOrEqual(3);
  });
});
