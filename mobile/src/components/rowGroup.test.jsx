import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

const h = vi.hoisted(() => ({ platform: { OS: 'ios' }, mode: 'light' }));

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
vi.mock('./Icon', () => ({ Icon: () => null }));
vi.mock('./Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    mode: h.mode,
    colors: { ink: '#000', ink3: '#666', ink4: '#999', danger: '#f00', bgPane: '#151515', card: '#f4f4f4', line: '#ddd', selected: '#eee' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoSemibold: 'ms' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
  }),
}));

const { Row, RowGroup, RowSeparator, SectionHeader, SettingsBand, groupTone } = await import('./Row');
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
});

describe('RowGroup', () => {
  it.each([['light', '#f4f4f4'], ['dark', '#f4f4f4']])('draws the %s group one tone off the ground with 4 pt corners', (mode, tone) => {
    h.mode = mode;
    const { container } = render(<RowGroup><Row label="Model" /></RowGroup>);
    const group = styleOf(container.firstChild);
    expect(group).toMatchObject({ backgroundColor: tone, borderRadius: 4, overflow: 'hidden', marginHorizontal: 16 });
    expect(groupTone({ card: '#f4f4f4' })).toBe(tone);
  });

  it('hands its tone to whatever mixes against the ground inside it', () => {
    const { container } = render(
      <>
        <RowGroup><Ground /></RowGroup>
        <Ground />
      </>,
    );
    const grounds = [...container.querySelectorAll('[data-ground]')].map((n) => n.dataset.ground);
    expect(grounds).toEqual(['#f4f4f4', '#151515']);
  });

  it('rings today\'s usage bar on the group tone, not the pane', () => {
    const days = toUsageDays([{ iso: '2026-06-29', tokIn: 1000, tokOut: 500, cost: 0.12, today: true }]);
    const { container } = render(<RowGroup><UsageChart days={days} accent="#3899e2" /></RowGroup>);
    const ring = [...container.querySelectorAll('[data-style]')].map(styleOf).find((s) => s.borderWidth === 1.5);
    expect(ring.backgroundColor).toBe('#f4f4f4');
  });
});

describe('phone gutter', () => {
  it('puts the section label and the card edge on the same 16 pt gutter, and the row text 16 inside the card', () => {
    const { container } = render(
      <>
        <SectionHeader>Overview</SectionHeader>
        <RowGroup><Row label="Model" /></RowGroup>
      </>,
    );
    const [label, card] = [...container.children].map(styleOf);
    expect(label.paddingHorizontal).toBe(16);
    expect(card.marginHorizontal).toBe(16);
    const row = [...container.querySelectorAll('[data-style]')].map(styleOf).find((x) => x.flexDirection === 'row');
    expect(row.paddingHorizontal).toBe(16);
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
    expect(row.paddingHorizontal).toBe(16);
    expect(styles.find((s) => s.height === 0.5)).toEqual({ height: 0.5, backgroundColor: '#ddd', marginLeft: 16 });
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
