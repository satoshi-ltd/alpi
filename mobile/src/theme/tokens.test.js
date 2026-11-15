import { BRAND_INK } from '../../../common/shapes.mjs';
import { describe, expect, it } from 'vitest';

import { floatShadow, palettes, shadows, veils } from './tokens';

const MODES = ['light', 'dark'];

const CONSUMED_KEYS = [
  'accent',
  'bg',
  'bgElev',
  'bgInput',
  'bgPane',
  'bgSide',
  'card',
  'danger',
  'field',
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

  it('keeps every surface and shadow colour an equal-channel grey', () => {
    for (const mode of ['light', 'dark']) for (const key of ['bg', 'bgPane', 'bgSide', 'bgElev', 'fill', 'raised']) expect(grey(palettes[mode][key]), key).toBe(true);
    for (const mode of ['light', 'dark']) {
      for (const level of Object.values(shadows[mode])) expect(grey(level.shadowColor.length === 4 ? `#${[...level.shadowColor.slice(1)].map((c) => c + c).join('')}` : level.shadowColor)).toBe(true);
    }
  });
});

describe('floating surfaces on the phone', () => {
  it.each(['light', 'dark'])('leaves base and sm flat with no border in %s, since the phone draws no hairlines', (mode) => {
    for (const name of ['base', 'sm']) {
      expect(shadows[mode][name].shadowOpacity).toBe(0);
      expect(shadows[mode][name].borderWidth).toBe(0);
      expect(shadows[mode][name]).not.toHaveProperty('borderTopWidth');
    }
  });

  it('floats light sheets, dialogs, popovers and toasts on a soft shadow with no edge', () => {
    expect(floatShadow.light).toMatch(/0 12px 32px/);
    for (const name of ['sheet', 'dialog', 'popover', 'toast']) {
      const level = shadows.light[name];
      expect(level.shadowOpacity, name).toBeCloseTo(0.1);
      expect(level.shadowRadius, name).toBeGreaterThan(0);
      expect(level.shadowOffset.height, name).toBe(12);
      expect(level.borderWidth, name).toBe(0);
    }
  });

  it('edges dark floats with the one 1 pt hairline of the board and a deep shadow', () => {
    expect(floatShadow.dark).toMatch(/0 0 0 1px rgba\(237, 237, 237, 0\.09\)/);
    for (const name of ['sheet', 'dialog', 'popover', 'toast']) {
      const level = shadows.dark[name];
      expect(level.borderWidth, name).toBe(1);
      expect(level.borderColor, name).toBe('rgba(237,237,237,0.09)');
      expect(level.shadowOpacity, name).toBeCloseTo(0.55);
    }
  });
});

describe('paper dialogs on the phone', () => {
  it('cuts sheets with the 28 pt sheet corner and dims the screen with the veil', async () => {
    const { radii, veil } = await import('./tokens');
    expect(radii.sheet).toBe(28);
    expect(radii.xs).toBe(6);
    expect(veil(palettes.light)).toBe(veils.light);
    expect(veil(palettes.dark)).toBe(veils.dark);
    expect(veils.light).toBe('rgba(20, 20, 20, 0.22)');
    expect(veils.dark).toBe('rgba(0, 0, 0, 0.55)');
  });

  it('leaves no dark scrim behind a sheet, a prompt or a confirm', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    for (const file of ['Sheet.jsx', 'ActionSheet.jsx', 'TextPrompt.jsx', 'ConfirmDialog.jsx']) {
      const source = readFileSync(join(import.meta.dirname, '../components', file), 'utf8');
      expect(source, file).not.toMatch(/rgba\(0,0,0,0\.45\)/);
      expect(source, file).toMatch(/backgroundColor: (popover \? 'transparent' : )?veil\(colors\)/);
      expect(source, file).not.toMatch(/shadow\.float/);
    }
  });

  it('grades every floating surface to its own shadow level', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const read = (rel) => readFileSync(join(import.meta.dirname, '..', rel), 'utf8');
    expect(read('components/Sheet.jsx')).toMatch(/twoPane \? shadow\.dialog : shadow\.sheet/);
    expect(read('components/ActionSheet.jsx')).toMatch(/twoPane \? shadow\.dialog : shadow\.sheet/);
    expect(read('components/ConfirmDialog.jsx')).toMatch(/\.\.\.shadow\.dialog/);
    expect(read('components/TextPrompt.jsx')).toMatch(/\.\.\.shadow\.dialog/);
    expect(read('components/Toast.jsx')).toMatch(/\.\.\.shadow\.toast/);
    expect(read('features/chat/MentionPopover.jsx')).toMatch(/\.\.\.shadow\.popover/);
    expect(read('features/chat/JumpToLatest.jsx')).toMatch(/\.\.\.shadow\.popover/);
    expect(shadows.light).not.toHaveProperty('float');
  });

  it('floats every sheet, dialog, prompt, toast and popover on the raised surface, one step over the fills it covers', async () => {
    const { readdirSync, readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const walk = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(join(dir, e.name)) : /\.jsx$/.test(e.name) && !/\.test\./.test(e.name) ? [join(dir, e.name)] : []));
    const floats = walk(join(import.meta.dirname, '..')).filter((path) => /shadow\.(dialog|popover|toast|sheet)\b/.test(readFileSync(path, 'utf8')));
    expect(floats.length).toBeGreaterThanOrEqual(7);
    for (const path of floats) {
      const source = readFileSync(path, 'utf8');
      expect(source, path).toMatch(/colors\.bgElev/);
      expect(source, path).not.toMatch(/backgroundColor: colors\.bgPane,\s*\n\s*(\.\.\.shadow|borderTopLeftRadius|borderRadius: radii\.sheet)/);
    }
    expect(palettes.light.bgElev).toBe(palettes.light.raised);
    expect(palettes.dark.bgElev).toBe(palettes.dark.raised);
    expect(luminance(palettes.dark.raised)).toBeGreaterThan(luminance(palettes.dark.fill));
  });
});
