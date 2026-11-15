import { describe, expect, it } from 'vitest';

import { ACCENT_HEXES } from '../../../common/accents.mjs';
import * as shared from '../../../common/tokens.mjs';
import {
  alpha,
  FONT_SIZE_ADDS,
  fonts,
  fontSizes,
  lineHeights,
  palettes,
  radii,
  space,
  status,
  surfaces,
  typography,
} from './tokens';
import * as mobileTokens from './tokens';

const MODES = ['light', 'dark'];

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
    expect(lineHeights).toBe(shared.lineHeights);
    expect(alpha).toBe(shared.alpha);
    expect(status).toBe(shared.status);
  });

  it('gives every shared spacing step and radius the shared value', () => {
    for (const [name, value] of Object.entries(shared.space)) expect(space[name], name).toBe(value);
    for (const [name, value] of Object.entries(shared.radii)) expect(radii[name], name).toBe(value);
  });

  it('adds nothing to the shared spacing or radius scales', () => {
    const extra = (mine, base) => Object.keys(mine).filter((name) => !(name in base));
    expect(extra(space, shared.space)).toEqual([]);
    expect(extra(radii, shared.radii)).toEqual([]);
    expect('spaceExtra' in shared).toBe(false);
  });

  it('puts every spacing step on the one 4 pt grid, restated here so the module cannot vouch for itself', () => {
    expect(Object.values(shared.spaceScale)).toEqual([4, 8, 12, 16, 24, 32, 48]);
    for (const [name, value] of Object.entries(space)) expect([4, 8, 12, 16, 24, 32, 48], name).toContain(value);
  });

  it('keeps fonts.mono a plain family string, since callers pass it straight to fontFamily', () => {
    expect(typeof fonts.mono).toBe('string');
    expect(typeof fonts.sans.regular).toBe('string');
  });
});

describe('type scale parity with the shared module', () => {
  it('adds only the chat alias, on the read rung, and drops nothing', () => {
    expect(FONT_SIZE_ADDS).toEqual({ chat: 16 });
    expect(Object.keys(shared.fontSizes).filter((name) => !(name in fontSizes))).toEqual([]);
    expect(Object.keys(fontSizes).filter((name) => !(name in shared.fontSizes))).toEqual(['chat']);
    expect(fontSizes.chat).toBe(shared.typeLadder.read);
  });

  it('keeps every shared step at the shared value', () => {
    for (const [name, value] of Object.entries(fontSizes)) {
      if (name in shared.fontSizes) expect(value, name).toBe(shared.fontSizes[name]);
    }
  });

  it('sets no text under the 12 pt floor at the default scale and only the six ladder rungs', () => {
    expect(Math.min(...Object.values(fontSizes))).toBe(12);
    expect(shared.typeFloor).toBe(12);
    expect([...new Set(Object.values(fontSizes))].sort((a, b) => a - b)).toEqual([12, 14, 15, 16, 20, 28]);
  });

  it('reads chat at 16 on both clients, the read rung', () => {
    expect(shared.fontSizes[shared.typography.chat.size]).toBe(16);
    expect(fontSizes[typography.chat.size]).toBe(16);
    expect(typography.chat.leading).toBe(shared.typography.chat.leading);
    const { chat: _mine, ...rest } = typography;
    const { chat: _shared, ...sharedRest } = shared.typography;
    expect(rest).toEqual(sharedRest);
  });
});

describe('palette parity with the shared module', () => {
  it('carries a shared twin for every mobile palette key and adds none of its own', () => {
    for (const mode of MODES) {
      expect(Object.keys(palettes[mode]).sort()).toEqual(Object.keys(shared.palettes[mode]).sort());
    }
  });

  it('installs no palette override: both clients draw the same surfaces', () => {
    expect(paletteMismatches()).toEqual({});
    expect('PALETTE_OVERRIDES' in mobileTokens).toBe(false);
    for (const mode of MODES) expect(surfaces[mode]).toEqual(shared.surfaces[mode]);
  });

  it('draws the four surfaces at the board values, restated here', () => {
    expect(surfaces.light).toEqual({ side: '#f6f6f6', pane: '#ffffff', fill: '#f2f2f2', raised: '#ffffff' });
    expect(surfaces.dark).toEqual({ side: '#121212', pane: '#1a1a1a', fill: '#262626', raised: '#2c2c2c' });
    expect(palettes.light.ink3).toBe('#6b6b6b');
    expect(palettes.dark.ink3).toBe('#969696');
  });

  it.each(MODES)('fills hover, selected and pressed from the shared state fills in %s', (mode) => {
    const { hover, selected, pressed } = palettes[mode];
    expect(alphaOf(hover)).toBe(shared.stateFills[mode].hover);
    expect(alphaOf(selected)).toBe(shared.stateFills[mode].selected);
    expect(alphaOf(pressed)).toBe(shared.stateFills[mode].pressed);
  });

  it('retires every old corner token and keeps none of them on the phone', () => {
    expect(shared.retiredRadii).toEqual(['chip', 'tag', 'sm', 'md', 'lg', 'xl', '2xl', '3xl']);
    for (const name of shared.retiredRadii) expect(radii[name], name).toBeUndefined();
  });
});
