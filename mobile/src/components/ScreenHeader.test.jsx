import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ pathname: '/', canGoBack: vi.fn(() => true) }));

vi.mock('expo-router', () => ({
  usePathname: () => h.pathname,
  useRouter: () => ({ canGoBack: h.canGoBack }),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, numberOfLines, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, hitSlop, style, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...p }, children);
  return { View, Text, Pressable };
});

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink2: '#333', ink3: '#666', bg: '#fff', line: '#eee' },
    fonts: { sans: { semibold: 'Inter_600SemiBold' }, mono: 'JetBrainsMono_400Regular' },
    fontSizes: { xs: 11, lg: 15 },
  }),
}));

vi.mock('./Icon', () => ({ Icon: ({ name }) => React.createElement('span', {}, name) }));

import { PaneContext } from '../nav/PaneContext';
import { ScreenHeader } from './ScreenHeader';

function inTwoPane(node) {
  return render(<PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>{node}</PaneContext.Provider>);
}

beforeEach(() => {
  h.pathname = '/';
  h.canGoBack.mockClear().mockReturnValue(true);
});

describe('ScreenHeader back chevron', () => {
  it('renders the chevron outside any pane provider', () => {
    render(<ScreenHeader title="Outputs" onBack={() => {}} />);
    expect(screen.getByText('back')).toBeTruthy();
  });

  it('drops the chevron at a pane root in two-pane mode', () => {
    h.pathname = '/chat/doc';
    inTwoPane(<ScreenHeader title="Chat" onBack={() => {}} />);
    expect(screen.queryByText('back')).toBeNull();
    expect(screen.getByText('Chat')).toBeTruthy();
  });

  it('drops the chevron on /outputs in two-pane mode — notifications are a pane root, like settings', () => {
    h.pathname = '/outputs';
    inTwoPane(<ScreenHeader title="Notifications" onBack={() => {}} />);
    expect(screen.queryByText('back')).toBeNull();
  });

  it('keeps the chevron on /outputs on the phone, where it was pushed over the roster', () => {
    h.pathname = '/outputs';
    render(<ScreenHeader title="Notifications" onBack={() => {}} />);
    expect(screen.getByText('back')).toBeTruthy();
  });

  it('keeps the chevron on a drilled screen in two-pane mode', () => {
    h.pathname = '/profile/doc/settings';
    inTwoPane(<ScreenHeader title="Settings" onBack={() => {}} />);
    expect(screen.getByText('back')).toBeTruthy();
  });

  it('drops the chevron without an onBack handler', () => {
    render(<ScreenHeader title="Outputs" />);
    expect(screen.queryByText('back')).toBeNull();
  });
});
