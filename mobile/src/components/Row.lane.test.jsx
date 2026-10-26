import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, testID }) => React.createElement('div', { 'data-id': testID, 'data-style': JSON.stringify([style].flat(Infinity).filter(Boolean).reduce((a, s) => ({ ...a, ...s }), {})) }, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, children);
  return { View, Text, Pressable };
});

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink3: '#666', ink4: '#999', danger: '#f00', bgPane: '#fff', selected: '#eee' },
    fonts: { sans: { regular: 'r' }, mono: 'm', monoMedium: 'mm' },
    fontSizes: { xs: 11, md: 14, lg: 15, xl: 18 },
  }),
}));
vi.mock('./Icon', () => ({ Icon: () => React.createElement('i', { 'data-icon': true }) }));

import { iconSizes } from '../theme/tokens';
import { Row } from './Row';

const lanes = (container) => [...container.querySelectorAll('[data-id="row-lane"]')];

describe('Row trailing lane', () => {
  it.each([
    ['with a chevron', { onPress: () => {} }, 1],
    ['without a press handler', {}, 0],
    ['disabled', { onPress: () => {}, disabled: true }, 0],
    ['danger', { onPress: () => {}, danger: true }, 0],
    ['with the chevron off', { onPress: () => {}, chevron: false }, 0],
  ])('reserves one 16 pt lane %s so trailing values share an edge', (_, props, icons) => {
    const { container } = render(<Row label="Model" value="opus" {...props} />);
    const found = lanes(container);
    expect(found).toHaveLength(1);
    expect(JSON.parse(found[0].dataset.style).width).toBe(iconSizes.md);
    expect(found[0].querySelectorAll('[data-icon]')).toHaveLength(icons);
  });
});
