import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { fontSizes, lineHeights, palettes, radii, space } from './tokens';

const DESKTOP = readFileSync(
  join(import.meta.dirname, '../../../desktop/src/styles/tokens.css'),
  'utf8',
);

function desktopScale(prefix) {
  const out = {};
  const re = new RegExp(`--${prefix}-([a-z0-9]+):\\s*([0-9.]+)(px)?;`, 'g');
  for (const m of DESKTOP.matchAll(re)) out[m[1]] = Number(m[2]);
  return out;
}

function blockBody(selector) {
  const head = selector.exec(DESKTOP);
  if (!head) return '';
  const open = DESKTOP.indexOf('{', head.index);
  let depth = 0;
  for (let i = open; i < DESKTOP.length; i += 1) {
    if (DESKTOP[i] === '{') depth += 1;
    else if (DESKTOP[i] === '}') {
      depth -= 1;
      if (depth === 0) return DESKTOP.slice(open + 1, i);
    }
  }
  return '';
}

const IS_COLOR = /^(#[0-9a-f]{3,8}|rgba?\([^)]*\))$/i;

const mobileKey = (cssName) =>
  cssName.replace(/^c-/, '').replace(/-([a-z0-9])/g, (_, c) => c.toUpperCase());

function colorVars(body) {
  const out = {};
  for (const m of body.matchAll(/--([a-z0-9-]+):\s*([^;]+);/g)) {
    const value = m[2].trim();
    if (IS_COLOR.test(value)) out[mobileKey(m[1])] = value;
  }
  return out;
}

function normalizeColor(raw) {
  const value = raw.trim().toLowerCase().replace(/\s+/g, '');
  const fn = value.match(/^rgba?\(([^)]*)\)$/);
  if (!fn) return value;
  return `rgba(${fn[1].split(',').map((n) => String(Number(n))).join(',')})`;
}

const desktopLight = () => colorVars(blockBody(/^:root\s*\{/m));
const desktopDarkMedia = () => colorVars(blockBody(/:root:not\(\[data-mode="light"\]\)\s*\{/));
const desktopDarkToggle = () => colorVars(blockBody(/^\[data-mode="dark"\]\s*\{/m));

function desktopPalettes() {
  const light = desktopLight();
  return { light, dark: { ...light, ...desktopDarkToggle() } };
}

const PALETTE_EXCEPTIONS = {
  'light.bg': [
    'desktop #eef0f2 vs mobile #ffffff',
    'desktop bg is the canvas its floating panes sit on; every mobile screen is edge-to-edge, so bg doubles as the pane',
  ],
  'light.bgInput': [
    'desktop #ffffff vs mobile #f1f3f5',
    'mobile consumers fill borderless buttons and chips with bgInput, which desktop white would erase on a white ground',
  ],
  'dark.bgInput': [
    'desktop #11151a vs mobile #1a1f26',
    'follows light.bgInput: mobile raises the input above bgElev where desktop recesses it below',
  ],
  'light.accent': [
    'desktop #b8954a vs mobile #9c7a33',
    'the desktop gold is 2.44:1 on the SyncBar track over white, so mobile darkens it to clear 3:1',
  ],
};

function paletteMismatches() {
  const desktop = desktopPalettes();
  const out = {};
  for (const mode of ['light', 'dark']) {
    for (const [key, value] of Object.entries(desktop[mode])) {
      const mine = palettes[mode][key];
      if (mine === undefined) continue;
      if (normalizeColor(mine) !== normalizeColor(value)) {
        out[`${mode}.${key}`] = `desktop ${normalizeColor(value)} vs mobile ${normalizeColor(mine)}`;
      }
    }
  }
  return out;
}

const alphaOf = (color) => Number(color.match(/rgba\([^)]*,([0-9.]+)\)/)[1]);

const MOBILE_ONLY = {
  radii: ['bubble', 'sheet'],
  space: ['s10', 's11'],
  fs: ['hero'],
};

function compare(prefix, mobile, mobileOnly = [], key = (n) => n) {
  const desktop = desktopScale(prefix);
  const mismatched = [];
  for (const [name, value] of Object.entries(mobile)) {
    if (mobileOnly.includes(name)) continue;
    const twin = desktop[key(name)];
    if (twin === undefined) continue;
    if (value !== twin) mismatched.push(`${name}: desktop ${twin} vs mobile ${value}`);
  }
  const undeclared = Object.keys(mobile).filter(
    (name) => desktop[key(name)] === undefined && !mobileOnly.includes(name),
  );
  return { mismatched, undeclared, desktop };
}

describe('token parity with the desktop client', () => {
  it('reads the desktop scales at all, so a silent parse failure cannot fake a pass', () => {
    expect(Object.keys(desktopScale('r')).length).toBeGreaterThan(4);
    expect(Object.keys(desktopScale('space')).length).toBeGreaterThan(8);
    expect(Object.keys(desktopScale('fs')).length).toBeGreaterThan(6);
    expect(Object.keys(desktopScale('lh')).length).toBeGreaterThan(3);
  });

  it('gives every shared radius name the value desktop gives it', () => {
    const { mismatched, undeclared } = compare('r', radii, [...MOBILE_ONLY.radii, 'pill']);
    expect(mismatched).toEqual([]);
    expect(undeclared).toEqual([]);
  });

  it('gives every shared spacing step the value desktop gives it', () => {
    const { mismatched, undeclared } = compare('space', space, MOBILE_ONLY.space, (n) => n.replace(/^s/, ''));
    expect(mismatched).toEqual([]);
    expect(undeclared).toEqual([]);
  });

  it('gives every shared font size the value desktop gives it', () => {
    const { mismatched, undeclared } = compare('fs', fontSizes, []);
    expect(mismatched).toEqual([]);
    expect(undeclared).toEqual([]);
  });

  it('gives every line height the value desktop gives it', () => {
    const { mismatched, undeclared } = compare('lh', lineHeights, []);
    expect(mismatched).toEqual([]);
    expect(undeclared).toEqual([]);
  });

  it('names the mobile-only steps so their absence from desktop is deliberate', () => {
    for (const name of MOBILE_ONLY.radii) expect(radii[name]).toBeGreaterThan(radii['3xl']);
    for (const name of MOBILE_ONLY.space) expect(space[name]).toBeGreaterThan(space.s9);
  });
});

describe('palette parity with the desktop client', () => {
  it('reads both desktop palettes at all, so a silent parse failure cannot fake a pass', () => {
    const { light, dark } = desktopPalettes();
    expect(Object.keys(light).length).toBeGreaterThanOrEqual(17);
    expect(Object.keys(desktopDarkToggle()).length).toBeGreaterThanOrEqual(13);
    for (const probe of ['bg', 'bgInput', 'ink', 'line', 'accent', 'success']) {
      expect(light[probe], probe).toMatch(/^(#|rgba)/);
      expect(dark[probe], probe).toMatch(/^(#|rgba)/);
    }
    expect(dark.bg).not.toBe(light.bg);
  });

  it('takes the dark values from a block that both desktop dark selectors agree on', () => {
    const media = desktopDarkMedia();
    expect(Object.keys(media).length).toBeGreaterThanOrEqual(13);
    expect(media).toEqual(desktopDarkToggle());
  });

  it('carries a desktop twin for every mobile palette key and no unmapped desktop colour', () => {
    const { light, dark } = desktopPalettes();
    expect(Object.keys(palettes.light).sort()).toEqual(Object.keys(light).sort());
    expect(Object.keys(palettes.dark).sort()).toEqual(Object.keys(dark).sort());
  });

  it('declares every colour divergence, with the exact pair each exception excuses', () => {
    const declared = Object.fromEntries(
      Object.entries(PALETTE_EXCEPTIONS).map(([key, [diff]]) => [key, diff]),
    );
    expect(paletteMismatches()).toEqual(declared);
  });

  it('gives every exception a one-line reason a reader can weigh', () => {
    for (const [key, [, reason]] of Object.entries(PALETTE_EXCEPTIONS)) {
      expect(reason, key).not.toContain('\n');
      expect(reason.length, key).toBeGreaterThan(30);
    }
  });

  it.each(['light', 'dark'])('keeps hover under selected under line in %s', (mode) => {
    const { hover, selected, line } = palettes[mode];
    expect(alphaOf(hover)).toBeLessThan(alphaOf(selected));
    expect(alphaOf(selected)).toBeLessThan(alphaOf(line));
  });
});
