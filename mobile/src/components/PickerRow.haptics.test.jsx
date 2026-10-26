import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ selection: vi.fn() }));
vi.mock('../lib/haptics', () => ({ selection: h.selection }));
vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', null, children);
  const Text = ({ children }) => React.createElement('span', null, children);
  const Pressable = ({ children, onPress, style }) => {
    style({ pressed: false });
    return React.createElement('button', { type: 'button', onClick: onPress }, children);
  };
  return { View, Text, Pressable, StyleSheet: { create: (s) => s } };
});
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink: '#000', ink3: '#666', accent: '#c90', selected: '#eee', line: '#ddd' }, fonts: { sans: { medium: 'm' }, mono: 'mono' }, fontSizes: { md: 15, xs: 11 } }),
}));
vi.mock('./Dot', () => ({ Dot: () => null }));

import { PickerRow } from './PickerRow';

describe('PickerRow haptics', () => {
  it('ticks a selection before running the choice', () => {
    const onPress = vi.fn();
    render(<PickerRow label="doc" onPress={onPress} />);
    fireEvent.click(screen.getByRole('button'));
    expect(h.selection).toHaveBeenCalledTimes(1);
    expect(onPress).toHaveBeenCalledTimes(1);
  });
});
