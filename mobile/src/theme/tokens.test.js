import { BRAND_INK } from '../../../common/folds.mjs';
import { describe, expect, it } from 'vitest';

import { PALETTE_OVERRIDES, palettes, shadows } from './tokens';

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

  it('keeps the accent tied to the brand ink of each theme', () => {
    expect(palettes.dark.accent).toBe(BRAND_INK.dark);
    expect(palettes.light.accent).toBe(BRAND_INK.light);
  });

  it.each(MODES)('clears 3:1 against the %s ground', (mode) => {
    expect(contrast(palettes[mode].accent, palettes[mode].bg)).toBeGreaterThanOrEqual(3);
  });

  it.each(MODES)('clears 3:1 against the %s SyncBar track', (mode) => {
    const ink = mode === 'light' ? '#141414' : '#ededed';
    const opacity = mode === 'light' ? 0.07 : 0.08;
    const bg = channels(palettes[mode].bg);
    const track = channels(ink)
      .map((c, i) => Math.round(c * opacity + bg[i] * (1 - opacity)))
      .reduce((hex, c) => hex + c.toString(16).padStart(2, '0'), '#');
    expect(contrast(palettes[mode].accent, track)).toBeGreaterThanOrEqual(3);
  });
});

describe('neutral greys on the phone', () => {
  const grey = (hex) => hex.length === 7 && hex.slice(1, 3) === hex.slice(3, 5) && hex.slice(3, 5) === hex.slice(5, 7);

  it('keeps every palette override and shadow colour an equal-channel grey', () => {
    for (const [path, [value]] of Object.entries(PALETTE_OVERRIDES)) expect(grey(value), path).toBe(true);
    for (const mode of ['light', 'dark']) {
      for (const level of Object.values(shadows[mode])) expect(grey(level.shadowColor.length === 4 ? `#${[...level.shadowColor.slice(1)].map((c) => c + c).join('')}` : level.shadowColor)).toBe(true);
    }
  });
});

describe('paper surfaces on the phone', () => {
  it.each(['light', 'dark'])('makes every %s elevation a hairline seam with no blur', (mode) => {
    for (const level of Object.values(shadows[mode])) {
      expect(level.shadowOpacity).toBe(0);
      expect(level.shadowRadius).toBe(0);
      expect(level.elevation).toBe(0);
      expect(level.borderWidth).toBe(0.5);
      expect([palettes[mode].line, palettes[mode].line2]).toContain(level.borderColor);
    }
  });
});

describe('paper dialogs on the phone', () => {
  it('cuts sheets with the 4 pt corner and veils the screen towards the ground', async () => {
    const { radii, veil } = await import('./tokens');
    expect(radii.sheet).toBeUndefined();
    expect(radii.xs).toBe(4);
    for (const mode of ['light', 'dark']) expect(veil(palettes[mode])).toBe(`${palettes[mode].bg}b8`);
  });

  it('leaves no dark scrim behind a sheet, a prompt or a confirm', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    for (const file of ['Sheet.jsx', 'ActionSheet.jsx', 'TextPrompt.jsx', 'TypedConfirm.jsx']) {
      const source = readFileSync(join(import.meta.dirname, '../components', file), 'utf8');
      expect(source, file).not.toMatch(/rgba\(0,0,0,0\.45\)/);
      expect(source, file).toMatch(/backgroundColor: veil\(colors\)/);
      expect(source, file).toMatch(/\.\.\.shadow\.base/);
    }
  });
});
