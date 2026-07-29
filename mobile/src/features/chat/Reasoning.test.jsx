import React from 'react';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, accessibilityLabel, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, ...p }, children);
  return { View, Text, Pressable, ScrollView: View, useWindowDimensions: () => ({ height: 800 }) };
});

vi.mock('react-native-svg', () => {
  const Noop = ({ children }) => React.createElement('span', null, children);
  return { default: Noop, Defs: Noop, LinearGradient: Noop, Rect: Noop, Stop: Noop };
});

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink3: '#666', ink4: '#999', line2: '#eee', bg: '#fff' },
    fonts: { mono: 'm' },
    fontSizes: { sm: 13, xs: 11 },
  }),
}));

vi.mock('../../components/Icon', () => ({
  Icon: ({ name }) => React.createElement('span', { 'data-icon': name }),
}));

import { Reasoning } from './Reasoning';

describe('Reasoning flat', () => {
  it('collapses to a thinking label with a peek, expands to the full text', () => {
    render(<Reasoning text={'line one\nline two'} seconds={12} flat />);
    expect(screen.getByText('thinking · 12s')).toBeTruthy();
    expect(screen.getByText('line two')).toBeTruthy();
    expect(screen.queryByText('line one')).toBeNull();
    fireEvent.click(screen.getByText('thinking · 12s').closest('button'));
    expect(screen.getByText('line one')).toBeTruthy();
  });

  it('renders nothing when finished with no text', () => {
    const { container } = render(<Reasoning text="" seconds={0} flat />);
    expect(container.textContent).toBe('');
  });
});
