import { describe, expect, it } from 'vitest';

import { ACCENT_HEXES } from '../../../common/accents.mjs';
import * as shared from '../../../common/tokens.mjs';
import { profileAccents } from './accents';
import {
  alpha,
  fonts,
  fontSizes,
  lineHeights,
  PALETTE_OVERRIDES,
  palettes,
  radii,
  space,
  status,
} from './tokens';

const MODES = ['light', 'dark'];

const MOBILE_ONLY = {
  radii: ['bubble', 'sheet'],
  space: ['s10', 's11'],
};

const EXPECTED_DIVERGENCES = {
  'light.bg': '#ffffff',
  'light.bgInput': '#f1f3f5',
  'dark.bgInput': '#1a1f26',
  'light.accent': '#9c7a33',
};

function paletteMismatches() {
  const out = {};
  for (const mode of MODES) {
    for (const [key, value] of Object.entries(shared.palettes[mode])) {
      const mine = palettes[mode][key];
      if (mine !== value) out[`${mode}.${key}`] = mine;
    }
  }
  return out;
}

const alphaOf = (color) => Number(color.match(/rgba\([^)]*,([0-9.]+)\)/)[1]);

describe('shared design tokens', () => {
  it('reads the shared module at all, so a resolution failure cannot fake a pass', () => {
    expect(Object.keys(shared.fontSizes).length).toBeGreaterThan(6);
    expect(Object.keys(shared.space).length).toBeGreaterThan(8);
    expect(Object.keys(shared.radii).length).toBeGreaterThan(4);
    expect(Object.keys(shared.lineHeights).length).toBeGreaterThan(3);
    expect(Object.keys(shared.palettes.light).length).toBeGreaterThanOrEqual(17);
  });

  it('re-exports the shared scales instead of restating their numbers', () => {
    expect(fontSizes).toBe(shared.fontSizes);
    expect(lineHeights).toBe(shared.lineHeights);
    expect(alpha).toBe(shared.alpha);
    expect(status).toBe(shared.status);
  });

  it('gives every shared spacing step and radius the shared value', () => {
    for (const [name, value] of Object.entries(shared.space)) expect(space[name], name).toBe(value);
    for (const [name, value] of Object.entries(shared.radii)) expect(radii[name], name).toBe(value);
  });

  it('adds nothing to the shared scales beyond the declared mobile-only steps', () => {
    const extra = (mine, base) => Object.keys(mine).filter((name) => !(name in base));
    expect(extra(space, shared.space).sort()).toEqual(MOBILE_ONLY.space);
    expect(extra(radii, shared.radii).sort()).toEqual(MOBILE_ONLY.radii);
  });

  it('names the mobile-only steps so their absence from the shared module is deliberate', () => {
    for (const name of MOBILE_ONLY.radii) expect(radii[name]).toBeGreaterThan(radii['3xl']);
    for (const name of MOBILE_ONLY.space) expect(space[name]).toBeGreaterThan(space.s9);
  });

  it('keeps fonts.mono a plain family string, since callers pass it straight to fontFamily', () => {
    expect(typeof fonts.mono).toBe('string');
    expect(typeof fonts.sans.regular).toBe('string');
  });
});

describe('palette parity with the shared module', () => {
  it('carries a shared twin for every mobile palette key and adds none of its own', () => {
    for (const mode of MODES) {
      expect(Object.keys(palettes[mode]).sort()).toEqual(Object.keys(shared.palettes[mode]).sort());
    }
  });

  it('declares every colour divergence, with the exact value each override installs', () => {
    const declared = Object.fromEntries(
      Object.entries(PALETTE_OVERRIDES).map(([path, [value]]) => [path, value]),
    );
    expect(paletteMismatches()).toEqual(declared);
  });

  it('diverges only where this test independently expects it, so the override table cannot vouch for itself', () => {
    expect(paletteMismatches()).toEqual(EXPECTED_DIVERGENCES);
  });

  it('gives every divergence a reason a reader can weigh', () => {
    for (const [path, [, reason]] of Object.entries(PALETTE_OVERRIDES)) {
      expect(path in EXPECTED_DIVERGENCES, `${path} is undeclared in this test`).toBe(true);
      expect(String(reason).length, `${path} has no reason`).toBeGreaterThan(30);
    }
  });

  it('leaves no stale override that no longer changes anything', () => {
    for (const [path, [value]] of Object.entries(PALETTE_OVERRIDES)) {
      const [mode, key] = path.split('.');
      expect(shared.palettes[mode][key], path).toBeDefined();
      expect(value, path).not.toBe(shared.palettes[mode][key]);
    }
  });

  it('gives every override a one-line reason a reader can weigh', () => {
    for (const [path, [, reason]] of Object.entries(PALETTE_OVERRIDES)) {
      expect(reason, path).not.toContain('\n');
      expect(reason.length, path).toBeGreaterThan(30);
    }
  });

  it.each(MODES)('keeps hover under selected under line in %s', (mode) => {
    const { hover, selected, line } = palettes[mode];
    expect(alphaOf(hover)).toBeLessThan(alphaOf(selected));
    expect(alphaOf(selected)).toBeLessThan(alphaOf(line));
  });
});

describe('profile accents', () => {
  it('draws every profile colour from the shared choosable set', () => {
    const outside = Object.entries(profileAccents).filter(([, hex]) => !ACCENT_HEXES.includes(hex));
    expect(outside).toEqual([]);
  });

  it('spends the whole choosable set, so no swatch is unreachable by a profile', () => {
    const used = new Set(Object.values(profileAccents));
    expect(ACCENT_HEXES.filter((hex) => !used.has(hex))).toEqual([]);
  });
});
