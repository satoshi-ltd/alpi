import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  const View = ({ children, style, accessibilityRole, ...p }) =>
    React.createElement('div', { ...p, role: accessibilityRole, 'data-style': JSON.stringify(flat(style)) }, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-style': JSON.stringify(flat(style)) }, children);
  const Pressable = ({ children, onPress, accessibilityLabel, style }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-style': JSON.stringify(flat(style)) }, children);
  return { View, Text, Pressable, StyleSheet: { hairlineWidth: 0.5 } };
});
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { hover: '#eee', line: '#ddd', danger: '#f00', ink: '#000', ink3: '#666' },
    fonts: { sans: { regular: 'r', semibold: 's' } },
    fontSizes: { sm: 12, md: 14 },
  }),
}));
vi.mock('./Icon', () => ({ Icon: ({ name, color }) => React.createElement('i', { 'data-icon': name, 'data-color': color }) }));

import { AlertBanner } from './AlertBanner';

const style = (node) => JSON.parse(node.getAttribute('data-style'));

describe('AlertBanner', () => {
  it('draws the hover ground inside a hairline, no side stripe, the danger triangle, a bold lead and a quiet detail', () => {
    const { container } = render(<AlertBanner lead="Does not pass lint" detail="line 4" />);
    const root = screen.getByRole('alert');
    expect(style(root).backgroundColor).toBe('#eee');
    expect(style(root).borderColor).toBe('#ddd');
    expect([...container.querySelectorAll('div')].some((n) => style(n).width === 2)).toBe(false);
    expect(container.querySelector('[data-icon="triangle-alert"]').getAttribute('data-color')).toBe('#f00');
    expect(style(screen.getByText('Does not pass lint')).fontFamily).toBe('s');
    expect(style(screen.getByText('line 4')).color).toBe('#666');
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('offers an action as a 44 pt target', () => {
    const onAction = vi.fn();
    render(<AlertBanner lead="x" action="Open" onAction={onAction} />);
    const btn = screen.getByRole('button', { name: 'Open' });
    expect(style(btn).minHeight).toBeGreaterThanOrEqual(44);
    fireEvent.click(btn);
    expect(onAction).toHaveBeenCalled();
  });
});
