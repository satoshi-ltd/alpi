import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const R = require('react');
  return {
    Pressable: ({ children, onPress, accessibilityLabel, accessibilityRole }) => R.createElement('button', { 'aria-label': accessibilityLabel, role: accessibilityRole, onClick: onPress }, typeof children === 'function' ? children({ pressed: false }) : children),
    Text: ({ children }) => R.createElement('span', null, children),
  };
});
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('i', { 'data-icon': name }) }));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink2: '#222', bgPane: '#fff', line2: '#ddd', selected: '#eee' }, fonts: { sans: { medium: 'm' } }, fontSizes: { sm: 12 }, shadow: { base: {} } }),
}));

import { JUMP_THRESHOLD, JumpToLatest } from './JumpToLatest';

describe('JumpToLatest', () => {
  it('stays hidden near the tail and jumps when far from it', () => {
    const onPress = vi.fn();
    const { rerender } = render(<JumpToLatest visible={false} onPress={onPress} />);
    expect(screen.queryByRole('button')).toBeNull();
    rerender(<JumpToLatest visible onPress={onPress} />);
    fireEvent.click(screen.getByRole('button', { name: 'Jump to latest' }));
    expect(onPress).toHaveBeenCalledTimes(1);
    expect(JUMP_THRESHOLD).toBeGreaterThan(0);
  });
});
