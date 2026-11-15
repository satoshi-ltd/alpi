import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { palettes } from '../../../common/tokens.mjs';

afterEach(cleanup);

const h = vi.hoisted(() => ({ copy: vi.fn(async () => true), toast: vi.fn() }));

vi.mock('react-native', () => {
  const flat = (style) => (typeof style === 'function' ? style({ pressed: false }) : style) ?? {};
  const View = ({ children, style, testID }) => React.createElement('div', { 'data-testid': testID, 'data-style': JSON.stringify(flat(style)) }, children);
  const Text = ({ children, style, numberOfLines, accessibilityRole }) =>
    React.createElement('span', { role: accessibilityRole === 'header' ? 'heading' : undefined, 'data-lines': numberOfLines ?? '', 'data-style': JSON.stringify(flat(style)) }, children);
  const Pressable = ({ children, onPress, style, accessibilityLabel, accessibilityState }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'aria-selected': accessibilityState?.selected, 'data-style': JSON.stringify(flat(style)) }, children);
  return { View, Text, Pressable };
});
vi.mock('../lib/clipboard', () => ({ copyText: h.copy }));
vi.mock('./Toast', () => ({ useToast: () => h.toast }));
vi.mock('./Icon', () => ({ Icon: ({ name }) => React.createElement('i', { 'data-icon': name }) }));
vi.mock('../theme/ThemeContext', async () => {
  const tokens = await import('../theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink: '#000', ink2: '#222', ink3: '#666', danger: '#f00', dangerText: '#a00', selected: '#eee', pressed: '#ddd', line2: '#ccc', hover: '#f4f4f4' },
      fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoMedium: 'monoM', monoSemibold: 'monoS' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

import { PanelRow, ROW_PAD } from './PanelRow';
import { DetailHead } from './DetailHead';
import { FACT_LABEL_W, FactCode, FactTable } from './FactTable';

const style = (el) => JSON.parse(el.getAttribute('data-style'));

describe('one panel row on the phone', () => {
  it('sets a 15 medium title, a 14 ink-3 second line up to two lines, a 12 tabular meta, padding 12 × 16 and a 44 pt target', () => {
    render(<PanelRow title="hotel-intake" sub="Turns a hotel link into a brief." meta="4.2 KB" onPress={() => {}} />);
    const button = screen.getByRole('button');
    expect(style(button)).toMatchObject({ minHeight: 44, paddingHorizontal: 16, paddingVertical: 12 });
    expect(ROW_PAD).toEqual({ horizontal: 16, vertical: 12 });
    const [title, meta, sub] = button.querySelectorAll('span');
    expect(style(title)).toMatchObject({ fontFamily: 'm', fontSize: 15, lineHeight: 20, color: '#000' });
    expect(title.getAttribute('data-lines')).toBe('1');
    expect(style(meta)).toMatchObject({ fontSize: 12, fontVariant: ['tabular-nums'], color: '#666' });
    expect(style(sub)).toMatchObject({ fontSize: 14, lineHeight: 18, color: '#666' });
    expect(sub.getAttribute('data-lines')).toBe('2');
    for (const span of [title, meta, sub]) expect(style(span).fontFamily).not.toMatch(/mono/);
    expect(button.getAttribute('data-style')).not.toMatch(/opacity/);
  });

  it('lifts line 2 and the meta to ink-2 when selected, and keeps an off title at ink-2', () => {
    render(<PanelRow title="Nudge" sub="Pings after a quiet week" meta="paused" off selected onPress={() => {}} />);
    const button = screen.getByRole('button');
    expect(style(button).backgroundColor).toBe('#eee');
    const [title, meta, sub] = button.querySelectorAll('span');
    expect(style(title).color).toBe('#222');
    expect(style(meta).color).toBe('#222');
    expect(style(sub).color).toBe('#222');
  });

  it('lets a failed state word take the meta in danger and draws the memory meter as a third line', () => {
    render(<PanelRow title="Learned" meta="over" metaTone="danger" bar={{ pct: 104, over: true }} onPress={() => {}} />);
    const [, meta] = screen.getByRole('button').querySelectorAll('span');
    expect(style(meta).color).toBe('#a00');
    const bar = screen.getByTestId('row-bar');
    expect(style(bar).height).toBe(3);
    expect(style(bar.firstChild)).toMatchObject({ width: '100%', backgroundColor: '#f00' });
  });

  it('keeps ink-2 on the selected fill at 4.5:1 in both themes', () => {
    const lum = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)).reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
    const over = (rgba, ground) => {
      const [r, g, b, a] = rgba.slice(rgba.indexOf('(') + 1, -1).split(',').map(Number);
      return `#${[r, g, b].map((c, i) => Math.round(c * a + parseInt(ground.slice(1 + i * 2, 3 + i * 2), 16) * (1 - a)).toString(16).padStart(2, '0')).join('')}`;
    };
    for (const mode of ['light', 'dark']) {
      const p = palettes[mode];
      const [hi, lo] = [lum(p.ink2), lum(over(p.selected, p.card))].sort((x, y) => y - x);
      expect((hi + 0.05) / (lo + 0.05), mode).toBeGreaterThanOrEqual(4.5);
    }
  });
});

describe('one detail header on the phone', () => {
  it('titles the page, states the word in ink-3 and copies the mono id', async () => {
    render(<DetailHead title="Weekly listing refresh" state="failed" stateTone="danger" id="a3f9c21e" />);
    expect(screen.getByRole('heading').textContent).toBe('Weekly listing refresh');
    expect(style(screen.getByText('failed'))).toMatchObject({ fontSize: 14, color: '#a00' });
    expect(style(screen.getByText('a3f9c21e'))).toMatchObject({ fontFamily: 'mono', fontSize: 13, color: '#666' });
    const copy = screen.getByRole('button', { name: 'Copy a3f9c21e' });
    expect(style(copy)).toMatchObject({ width: 44, height: 44 });
    await act(async () => { fireEvent.click(copy); });
    expect(h.copy).toHaveBeenCalledWith('a3f9c21e');
    expect(h.toast).toHaveBeenCalledWith({ message: 'Copied', kind: 'success' });
  });
});

describe('one facts table on the phone', () => {
  it('labels at 14 ink-3 in a 72 pt column, values 14 ink-2, mono only for ids, empty facts dropped', () => {
    render(<FactTable rows={[{ label: 'About', value: 'Compares every listing' }, { label: 'Next', value: null }, { label: 'Tools', value: [<FactCode key="a">web_fetch</FactCode>] }]} />);
    expect(FACT_LABEL_W).toBe(72);
    const about = screen.getByText('About');
    expect(style(about)).toMatchObject({ width: 72, fontSize: 14, color: '#666' });
    expect(style(screen.getByText('Compares every listing'))).toMatchObject({ fontSize: 14, color: '#222', fontFamily: 'r' });
    expect(style(screen.getByText('web_fetch')).fontFamily).toBe('mono');
    expect(screen.queryByText('Next')).toBeNull();
  });
});
