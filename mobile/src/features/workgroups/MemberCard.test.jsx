import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const plain = ({ style, numberOfLines, accessibilityRole, accessibilityState, accessibilityLabel, ...rest }) => ({
    ...rest,
    'data-lines': numberOfLines,
    'aria-label': accessibilityLabel,
  });
  const View = ({ children, ...p }) => React.createElement('div', plain(p), children);
  const Text = ({ children, ...p }) => React.createElement('span', plain(p), children);
  const Pressable = ({ children, onPress, ...p }) => React.createElement('button', { type: 'button', onClick: onPress, ...plain(p) }, children);
  return { View, Text, Pressable, StyleSheet: { create: (s) => s } };
});
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink2: '#333', ink3: '#666', hover: '#f4f4f4' },
    fonts: { mono: 'm', sans: { regular: 's', semibold: 'sb' } },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
  }),
}));
vi.mock('../../components/Fold', () => ({ Fold: ({ fold }) => React.createElement('i', { 'data-fold': fold }) }));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('i', { 'data-icon': name }) }));
vi.mock('../../components/Crease', () => ({ Crease: ({ text }) => React.createElement('b', null, text) }));

import { MemberCard } from './MemberCard';

describe('MemberCard', () => {
  it('shows the crease name, one bio line that expands, the owned phases and a row menu', () => {
    const onMore = vi.fn();
    render(<MemberCard label="@pixel" accent="#2cb3b5" fold="rocket" bio="Builds the site." owns={['setup', 'build']} onMore={onMore} />);
    expect(screen.getByText('pixel')).toBeTruthy();
    expect(screen.getByText('#setup')).toBeTruthy();
    const bio = screen.getByText('Builds the site.');
    expect(bio.getAttribute('data-lines')).toBe('1');
    fireEvent.click(bio);
    expect(screen.getByText('Builds the site.').getAttribute('data-lines')).toBeNull();
    fireEvent.click(screen.getByLabelText('More for @pixel'));
    expect(onMore).toHaveBeenCalled();
  });

  it('says the hub routes every phase instead of owning one', () => {
    render(<MemberCard label="@mira" accent="#6572e4" fold="crown" isHub owns={[]} />);
    expect(screen.getByText('hub')).toBeTruthy();
    expect(screen.getByText('none · the hub routes every phase')).toBeTruthy();
    expect(screen.queryByLabelText(/More for/)).toBeNull();
  });

  it('shows no owns line when the phases a member owns are unknown', () => {
    render(<MemberCard label="@remote" bio="Remote peer." />);
    expect(screen.queryByText('owns')).toBeNull();
  });
});
