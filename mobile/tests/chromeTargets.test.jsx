import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => ({
  Pressable: ({ children, style, accessibilityLabel }) =>
    React.createElement('button', { 'aria-label': accessibilityLabel, 'data-h': String((typeof style === 'function' ? style({ pressed: false }) : style).height) },
      typeof children === 'function' ? children({ pressed: false }) : children),
  Text: ({ children, maxFontSizeMultiplier }) => React.createElement('span', { 'data-cap': String(maxFontSizeMultiplier) }, children),
}));
vi.mock('../src/components/Icon', () => ({ Icon: () => null }));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({ colors: {}, fonts: { sans: {} }, fontSizes: { sm: 12 }, shadow: { base: {} }, chromeScale: 1.3 }),
}));

import { JumpToLatest } from '../src/features/chat/JumpToLatest';

describe('fixed-height chrome', () => {
  it('stands the Latest pill one touch target tall and caps its label at the chrome scale', () => {
    render(<JumpToLatest visible onPress={() => {}} />);
    expect(Number(screen.getByLabelText('Jump to latest').getAttribute('data-h'))).toBe(44);
    expect(screen.getByText('Latest').getAttribute('data-cap')).toBe('1.3');
  });
});
