import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

const h = vi.hoisted(() => ({ platform: { OS: 'ios' }, mode: 'light', wide: false }));

vi.mock('react-native', () => {
  const React = require('react');
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  const View = ({ children, style }) => React.createElement('div', { 'data-style': JSON.stringify(flat(style)) }, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const at = (style, pressed) => flat(typeof style === 'function' ? style({ pressed }) : style);
  const Pressable = ({ children, style }) =>
    React.createElement(
      'button',
      { 'data-idle': JSON.stringify(at(style, false)), 'data-pressed': JSON.stringify(at(style, true)) },
      children,
    );
  return { View, Text, Pressable, Platform: h.platform };
});
vi.mock('../nav/SettingsSurface', () => ({ useWideSettings: () => h.wide }));
vi.mock('./Icon', () => ({ Icon: () => null }));
vi.mock('./Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    mode: h.mode,
    colors: { ink: '#000', ink3: '#666', ink4: '#999', danger: '#f00', bgPane: '#151515', bgSide: '#f6f6f6', line: '#ddd', selected: '#eee' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoSemibold: 'ms' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
  }),
}));

const { Row, RowGroup, RowSeparator, SettingsBand, groupTone } = await import('./Row');
const { useGroundTone } = await import('./groupTone');
const { UsageChart } = await import('./UsageChart');
const { toUsageDays } = await import('../../../common/usage.mjs');
const styleOf = (node) => JSON.parse(node.dataset.style);

function Ground() {
  return <span data-ground={useGroundTone()} />;
}

afterEach(() => {
  cleanup();
  h.mode = 'light';
  h.wide = false;
});

describe('RowGroup', () => {
  it.each([['light', '#f6f6f6'], ['dark', '#151515']])('draws the %s group one tone off the ground with 4 pt corners', (mode, tone) => {
    h.mode = mode;
    const { container } = render(<RowGroup><Row label="Model" /></RowGroup>);
    const group = styleOf(container.firstChild);
    expect(group).toMatchObject({ backgroundColor: tone, borderRadius: 4, overflow: 'hidden', marginHorizontal: 12 });
    expect(groupTone({ bgPane: '#151515', bgSide: '#f6f6f6' }, mode)).toBe(tone);
  });

  it('hands its tone to whatever mixes against the ground inside it', () => {
    const { container } = render(
      <>
        <RowGroup><Ground /></RowGroup>
        <Ground />
      </>,
    );
    const grounds = [...container.querySelectorAll('[data-ground]')].map((n) => n.dataset.ground);
    expect(grounds).toEqual(['#f6f6f6', '#151515']);
  });

  it('rings today\'s usage bar on the group tone, not the pane', () => {
    const days = toUsageDays([{ iso: '2026-06-29', tokIn: 1000, tokOut: 500, cost: 0.12, today: true }]);
    const { container } = render(<RowGroup><UsageChart days={days} accent="#3899e2" /></RowGroup>);
    const ring = [...container.querySelectorAll('[data-style]')].map(styleOf).find((s) => s.borderWidth === 1.5);
    expect(ring.backgroundColor).toBe('#f6f6f6');
  });

  it('passes its children through untouched on wide settings', () => {
    h.wide = true;
    const { container } = render(<RowGroup><span data-child="" /></RowGroup>);
    expect(container.firstChild.dataset.child).toBe('');
  });
});

describe('phone rows inside a group', () => {
  it('leave the row, separator and band transparent so the group shows through', () => {
    const { container } = render(
      <>
        <Row label="Model" value="deepseek" />
        <RowSeparator />
        <SettingsBand><span /></SettingsBand>
      </>,
    );
    const styles = [...container.querySelectorAll('[data-style]')].map(styleOf);
    const row = styles.find((s) => s.flexDirection === 'row');
    expect(row.backgroundColor).toBeUndefined();
    expect(row.marginHorizontal).toBeUndefined();
    expect(row.paddingHorizontal).toBe(20);
    expect(styles.find((s) => s.height === 0.5)).toEqual({ height: 0.5, backgroundColor: '#ddd', marginLeft: 20 });
    expect(styles.find((s) => s.paddingVertical === 16).backgroundColor).toBeUndefined();
  });

  it('paints the pressed tint on the row itself', () => {
    const { container } = render(<RowGroup><Row label="Model" onPress={() => {}} /></RowGroup>);
    const button = container.querySelector('button');
    expect(JSON.parse(button.dataset.idle).backgroundColor).toBe('transparent');
    expect(JSON.parse(button.dataset.pressed).backgroundColor).toBe('#eee');
    expect(button.parentElement).toBe(container.firstChild);
    expect(styleOf(button.firstChild).backgroundColor).toBeUndefined();
  });

  it('leaves the pressed tint to the ripple on Android so the row is not tinted twice', () => {
    h.platform.OS = 'android';
    const { container } = render(<RowGroup><Row label="Model" onPress={() => {}} /></RowGroup>);
    expect(JSON.parse(container.querySelector('button').dataset.pressed).backgroundColor).toBe('transparent');
    h.platform.OS = 'ios';
  });
});
