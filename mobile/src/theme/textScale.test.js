import { describe, expect, it } from 'vitest';

import {
  clampTextScale,
  DEFAULT_TEXT_SCALE,
  MAX_TEXT_SCALE,
  MIN_TEXT_SCALE,
  scaleFontSizes,
  stepTextScale,
  TEXT_SCALES,
  textScaleLabel,
} from './textScale';
import { fontSizes } from './tokens';

const KEYS = Object.keys(fontSizes);

describe('text scale steps', () => {
  it('offers a bounded, ordered, uniquely labelled set', () => {
    const values = TEXT_SCALES.map((step) => step.value);
    expect(values).toEqual([...values].sort((a, b) => a - b));
    expect(new Set(values).size).toBe(values.length);
    expect(new Set(TEXT_SCALES.map((step) => step.label)).size).toBe(values.length);
    expect(values[0]).toBe(MIN_TEXT_SCALE);
    expect(values[values.length - 1]).toBe(MAX_TEXT_SCALE);
    expect(values).toContain(DEFAULT_TEXT_SCALE);
  });

  it('clamps at both ends instead of running off the scale', () => {
    expect(clampTextScale(99)).toBe(MAX_TEXT_SCALE);
    expect(clampTextScale(0.1)).toBe(MIN_TEXT_SCALE);
    expect(clampTextScale(-3)).toBe(MIN_TEXT_SCALE);
  });

  it('falls back to the default for anything that is not a number', () => {
    expect(clampTextScale('nope')).toBe(DEFAULT_TEXT_SCALE);
    expect(clampTextScale(undefined)).toBe(DEFAULT_TEXT_SCALE);
    expect(clampTextScale(null)).toBe(DEFAULT_TEXT_SCALE);
    expect(clampTextScale('')).toBe(DEFAULT_TEXT_SCALE);
    expect(clampTextScale(true)).toBe(DEFAULT_TEXT_SCALE);
    expect(clampTextScale(NaN)).toBe(DEFAULT_TEXT_SCALE);
  });

  it('reads a persisted string back as its step', () => {
    expect(clampTextScale('1.15')).toBe(1.15);
    expect(clampTextScale('0.9')).toBe(0.9);
  });

  it('snaps an off-grid value to its nearest step', () => {
    expect(clampTextScale(1.02)).toBe(1);
    expect(clampTextScale(1.2)).toBe(1.15);
  });

  it('steps one notch at a time and stops at the ends', () => {
    expect(stepTextScale(1, 1)).toBe(1.15);
    expect(stepTextScale(1, -1)).toBe(0.9);
    expect(stepTextScale(MIN_TEXT_SCALE, -1)).toBe(MIN_TEXT_SCALE);
    expect(stepTextScale(MAX_TEXT_SCALE, 1)).toBe(MAX_TEXT_SCALE);
  });

  it('walks the whole scale in both directions without drift', () => {
    let scale = MIN_TEXT_SCALE;
    for (let i = 0; i < TEXT_SCALES.length + 2; i += 1) scale = stepTextScale(scale, 1);
    expect(scale).toBe(MAX_TEXT_SCALE);
    for (let i = 0; i < TEXT_SCALES.length + 2; i += 1) scale = stepTextScale(scale, -1);
    expect(scale).toBe(MIN_TEXT_SCALE);
  });

  it('returns to the default on a zero direction, mirroring desktop cmd-0', () => {
    expect(stepTextScale(MAX_TEXT_SCALE, 0)).toBe(DEFAULT_TEXT_SCALE);
    expect(stepTextScale(MIN_TEXT_SCALE, 0)).toBe(DEFAULT_TEXT_SCALE);
  });

  it('names every step, including one reached from a stored off-grid value', () => {
    expect(textScaleLabel(1)).toBe('Default');
    expect(textScaleLabel(MAX_TEXT_SCALE)).toBe('Largest');
    expect(textScaleLabel('garbage')).toBe('Default');
  });
});

describe('scaleFontSizes', () => {
  it('leaves the default scale byte-identical to the raw tokens', () => {
    expect(scaleFontSizes(DEFAULT_TEXT_SCALE)).toEqual(fontSizes);
    for (const key of KEYS) expect(scaleFontSizes(DEFAULT_TEXT_SCALE)[key]).toBe(fontSizes[key]);
  });

  it('treats a missing or corrupt preference as the default scale', () => {
    expect(scaleFontSizes(undefined)).toEqual(fontSizes);
    expect(scaleFontSizes('nope')).toEqual(fontSizes);
  });

  it('multiplies every token, leaving none behind', () => {
    const larger = scaleFontSizes(MAX_TEXT_SCALE);
    expect(Object.keys(larger)).toEqual(KEYS);
    for (const key of KEYS) expect(larger[key]).toBeGreaterThan(fontSizes[key]);
    const smaller = scaleFontSizes(MIN_TEXT_SCALE);
    for (const key of KEYS) expect(smaller[key]).toBeLessThan(fontSizes[key]);
  });

  it('keeps the scale strictly ordered at every step so roles never collide', () => {
    const ordered = KEYS.map((key) => fontSizes[key]).every((size, i, all) => i === 0 || size > all[i - 1]);
    expect(ordered).toBe(true);
    for (const { value } of TEXT_SCALES) {
      const sizes = KEYS.map((key) => scaleFontSizes(value)[key]);
      expect(sizes.every((size, i) => i === 0 || size > sizes[i - 1])).toBe(true);
    }
  });

  it('rounds to whole pixels and never below the legibility floor', () => {
    for (const { value } of TEXT_SCALES) {
      for (const size of Object.values(scaleFontSizes(value))) {
        expect(Number.isInteger(size)).toBe(true);
        expect(size).toBeGreaterThanOrEqual(8);
      }
    }
  });

  it('clamps an out-of-range scale before it reaches the tokens', () => {
    expect(scaleFontSizes(99)).toEqual(scaleFontSizes(MAX_TEXT_SCALE));
    expect(scaleFontSizes(0.1)).toEqual(scaleFontSizes(MIN_TEXT_SCALE));
  });
});
