import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const { fontOf } = vi.hoisted(() => ({
  fontOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((f, s) => s.fontFamily ?? f, null),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, numberOfLines, ellipsizeMode, ...p }) =>
    React.createElement('span', { ...p, 'data-font': fontOf(style) }, children);
  const Pressable = ({ children, onPress, android_ripple, style, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...p }, children);
  return { View, Text, Pressable };
});

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink3: '#666', ink4: '#999', danger: '#f00', bgPane: '#fff', selected: '#eee' },
    fonts: {
      sans: { regular: 'Inter_400Regular' },
      mono: 'JetBrainsMono_400Regular',
      monoMedium: 'JetBrainsMono_500Medium',
    },
    fontSizes: { xs: 11, md: 14, lg: 15, xl: 18 },
  }),
}));

import { iconSizes } from '../theme/tokens';
import { Row, SectionHeader } from './Row';

describe('Row typography', () => {
  it('renders every string in a theme font, chevron included', () => {
    const { container } = render(<Row label="Connections" helper="two paired" value="alpi-casa" onPress={() => {}} />);
    expect(screen.getByText('Connections').getAttribute('data-font')).toBe('Inter_400Regular');
    expect(screen.getByText('two paired').getAttribute('data-font')).toBe('JetBrainsMono_500Medium');
    expect(screen.getByText('alpi-casa').getAttribute('data-font')).toBe('Inter_400Regular');
    expect(container.querySelector('svg').getAttribute('width')).toBe(String(iconSizes.md));
  });

  it('renders the section header in the mono token', () => {
    render(<SectionHeader>servers</SectionHeader>);
    expect(screen.getByText('servers').getAttribute('data-font')).toBe('JetBrainsMono_500Medium');
  });
});
