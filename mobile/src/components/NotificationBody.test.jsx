import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const openURL = vi.fn(() => Promise.resolve());

vi.mock('react-native', () => {
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  const View = ({ children, style }) => React.createElement('div', { 'data-style': JSON.stringify(flat(style)) }, children);
  const Text = ({ children, style, onPress, accessibilityRole }) =>
    React.createElement(onPress ? 'button' : 'span', { type: onPress ? 'button' : undefined, onClick: onPress, role: accessibilityRole, 'data-style': JSON.stringify(flat(style)) }, children);
  const Pressable = ({ children, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, children);
  const ScrollView = ({ children }) => React.createElement('div', null, children);
  return { View, Text, Pressable, ScrollView, Linking: { openURL: (...args) => openURL(...args) }, StyleSheet: { hairlineWidth: 0.5 } };
});
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { hover: '#eee', line: '#ddd', danger: '#f00', ink: '#000', ink2: '#333', ink3: '#666', bgPane: '#fff' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
    fontSizes: { sm: 12, md: 14, lg: 16, xl: 18 },
  }),
}));
vi.mock('./Icon', () => ({ Icon: ({ name }) => React.createElement('i', { 'data-icon': name }) }));
vi.mock('./Chart', () => ({ Chart: () => null }));
vi.mock('./Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('span', null, children) }));

import { NotificationBody } from './NotificationBody';

beforeEach(() => openURL.mockClear());

const style = (node) => JSON.parse(node.getAttribute('data-style'));

describe('NotificationBody links', () => {
  it('renders a markdown link and a bare URL as pressable links that open with Linking', () => {
    render(<NotificationBody body={'Ver [el anuncio](https://example.com/a) hoy.\nhttps://example.com/b.'} />);
    const named = screen.getByRole('link', { name: 'el anuncio' });
    expect(style(named).textDecorationLine).toBe('underline');
    fireEvent.click(screen.getByRole('link', { name: 'https://example.com/b' }));
    expect(openURL).toHaveBeenCalledWith('https://example.com/b');
  });

  it('keeps a URL inside code as code', () => {
    render(<NotificationBody body={'Usa `https://example.com/c` tal cual.'} />);
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText('https://example.com/c')).toBeTruthy();
  });
});
