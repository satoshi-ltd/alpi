import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', { ...p, 'data-vstyle': JSON.stringify(style) }, children);
  const Text = ({ children }) => React.createElement('span', null, children);
  const Pressable = ({ children, style, accessibilityState }) =>
    React.createElement('button', { 'data-tap': JSON.stringify(style({ pressed: false })), 'aria-selected': accessibilityState?.selected }, children);
  return { View, Text, Pressable, StyleSheet: { create: (s) => s } };
});

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink3: '#666', accent: '#c90', selected: '#eee', line: '#ddd' },
    fonts: { sans: { medium: 'm' }, mono: 'mono' },
    fontSizes: { md: 15, xs: 11 },
  }),
}));

vi.mock('./Dot', () => ({ Dot: ({ color }) => React.createElement('i', { 'data-dot': color }) }));

import { PICKER_TEXT_EDGE } from './PickerLead';
import { PickerRow } from './PickerRow';

describe('PickerRow lane', () => {
  it('puts the text edge at 42 from the gutter', () => {
    expect(PICKER_TEXT_EDGE).toBe(42);
  });

  it('draws the selected dot in the accent', () => {
    render(<PickerRow label="doc" selected onPress={() => {}} />);
    expect(document.querySelector('[data-dot]').getAttribute('data-dot')).toBe('#c90');
  });

  it('starts its separator exactly at the text edge', () => {
    render(<PickerRow label="doc" separator onPress={() => {}} />);
    const sep = JSON.parse(document.querySelector('[testid="picker-separator"]').getAttribute('data-vstyle'));
    expect(sep.marginLeft).toBe(42);
  });
});
