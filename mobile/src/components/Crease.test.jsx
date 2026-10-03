import React from 'react';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

import { contrastRatio, creaseTones } from '../../../common/crease.mjs';
import { fonts, palettes } from '../theme/tokens';
import { creaseWidth } from './creaseMetrics';

afterEach(cleanup);

const h = vi.hoisted(() => ({ mode: 'light', layout: null }));

vi.mock('react-native', () => {
  const View = ({ children, accessibilityRole, accessibilityLabel, accessible, style, onLayout, ...p }) => {
    h.layout = onLayout;
    return React.createElement('div', { role: accessibilityRole, 'aria-label': accessibilityLabel, ...p }, children);
  };
  const Text = ({ children, numberOfLines, accessible, style, ...p }) =>
    React.createElement('span', { 'data-plain': 'true', ...p }, children);
  return { View, Text };
});

vi.mock('../theme/ThemeContext', async () => {
  const tokens = await import('../theme/tokens');
  return { useTheme: () => ({ mode: h.mode, colors: tokens.palettes[h.mode], fonts: tokens.fonts }) };
});

const { Crease, creaseAxis, creaseStops } = await import('./Crease');

const stopsOf = () => [...document.querySelectorAll('stop')].map((s) => ({
  offset: Number(s.getAttribute('offset')),
  color: s.getAttribute('stop-color'),
  opacity: Number(s.getAttribute('stop-opacity')),
}));

describe('Crease', () => {
  it('names the wordmark for screen readers as a header', () => {
    const { getByRole } = render(<Crease text="doc" accent="#6572e4" size={28} />);
    expect(getByRole('header').getAttribute('aria-label')).toBe('doc');
  });

  it('paints the text with its own gradient', () => {
    render(<Crease text="doc" accent="#6572e4" size={28} />);
    const gradient = document.querySelector('linearGradient');
    const text = document.querySelector('text');
    expect(text.textContent).toBe('doc');
    expect(text.getAttribute('fill')).toBe(`url(#${gradient.getAttribute('id')})`);
    expect(text.getAttribute('font-family')).toBe('BricolageGrotesque_800ExtraBold');
    expect(text.getAttribute('font-weight')).toBeNull();
  });

  it('gives every instance its own gradient id', () => {
    render(<><Crease text="a" accent="#6572e4" /><Crease text="b" accent="#6572e4" /></>);
    const ids = [...document.querySelectorAll('linearGradient')].map((g) => g.getAttribute('id'));
    expect(new Set(ids).size).toBe(2);
    for (const id of ids) expect(id).toMatch(/^[A-Za-z0-9]+$/);
  });

  it.each(['light', 'dark'])('uses the three tones creaseTones picks for the %s ground', (mode) => {
    h.mode = mode;
    const accent = '#6572e4';
    render(<Crease text="doc" accent={accent} size={28} />);
    const tones = creaseTones(accent, palettes[mode].bg);
    const solid = stopsOf().filter((s) => s.opacity === 1).map((s) => s.color);
    expect([...new Set(solid)]).toEqual(tones);
    for (const tone of tones) expect(contrastRatio(tone, palettes[mode].bg)).toBeGreaterThanOrEqual(3);
  });

  it('falls back to readable neutral tones for a colour that is not a hex', () => {
    h.mode = 'light';
    render(<Crease text="doc" accent="red" size={28} />);
    const solid = [...new Set(stopsOf().filter((s) => s.opacity === 1).map((s) => s.color))];
    expect(solid).toHaveLength(3);
    for (const tone of solid) expect(contrastRatio(tone, palettes.light.bg)).toBeGreaterThanOrEqual(3);
  });

  it('keeps the stops ordered with a transparent slit between the bands', () => {
    const stops = creaseStops(['#111111', '#222222', '#333333'], 100);
    const offsets = stops.map((s) => s.offset);
    expect(offsets).toEqual([...offsets].sort((a, b) => a - b));
    expect(stops.filter((s) => s.opacity === 0)).toHaveLength(4);
    expect(stops[0].offset).toBe(0);
    expect(stops.at(-1).offset).toBe(1);
  });

  it('runs the gradient axis along the 115 degree crease through the box centre', () => {
    const { x1, y1, x2, y2 } = creaseAxis(100, 40);
    expect((x1 + x2) / 2).toBeCloseTo(50);
    expect((y1 + y2) / 2).toBeCloseTo(20);
    expect(x2).toBeGreaterThan(x1);
    expect(y2).toBeGreaterThan(y1);
  });
});

describe('crease font wiring', () => {
  it('loads the bundled face under the family name the theme exposes', () => {
    const layout = readFileSync(join(process.cwd(), 'app/_layout.jsx'), 'utf8');
    expect(layout).toContain(`${fonts.crease}: require('../assets/fonts/BricolageGrotesque-800.ttf')`);
    expect(existsSync(join(process.cwd(), 'assets/fonts/BricolageGrotesque-800.ttf'))).toBe(true);
  });
});

describe('Crease width', () => {
  it.each([['@doc', 2.84], ['home', 2.8], ['moment', 4.17], ['#WORKGROUP', 7.27], ['wgmemory', 5.67], ['@ALPHA', 4.32]])(
    'never measures %s narrower than the font does',
    (name, em) => {
      expect(creaseWidth(name, 100)).toBeGreaterThanOrEqual(em * 100);
    },
  );

  it('counts anything outside ASCII as a full-width glyph', () => {
    expect(creaseWidth('日本語', 10)).toBeGreaterThanOrEqual(30);
    expect(creaseWidth('🙂', 10)).toBeGreaterThanOrEqual(10);
  });

  it('keeps the size when the name fits and scales it down when it does not', () => {
    render(<Crease text="home" accent="#6572e4" size={28} />);
    const natural = creaseWidth('home', 28);
    act(() => h.layout({ nativeEvent: { layout: { width: natural + 40 } } }));
    expect(document.querySelector('text').getAttribute('font-size')).toBe('28');
    act(() => h.layout({ nativeEvent: { layout: { width: Math.floor(natural * 0.9) } } }));
    const size = Number(document.querySelector('text').getAttribute('font-size'));
    expect(size).toBeLessThan(28);
    expect(size).toBeGreaterThanOrEqual(24);
    expect(creaseWidth('home', size)).toBeLessThanOrEqual(Math.floor(natural * 0.9));
  });

  it('falls back to a single ellipsised Geist line when the name cannot fit at 24 or more', () => {
    render(<Crease text="site-hotel-victoire" accent="#6572e4" size={28} />);
    act(() => h.layout({ nativeEvent: { layout: { width: 200 } } }));
    expect(document.querySelector('text')).toBeNull();
    expect(document.querySelector('[data-plain]').textContent).toBe('site-hotel-victoire');
  });
});
