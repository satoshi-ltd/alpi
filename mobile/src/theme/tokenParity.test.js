import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { fontSizes, lineHeights, radii, space } from './tokens';

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
