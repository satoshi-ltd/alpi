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
    fonts: { sans: { semibold: 'Geist_600SemiBold' }, mono: 'GeistMono_400Regular' },
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

describe('ScreenHeader meta strip', () => {
  const meta = (
    <>
      <span data-meta="model">deepseek-v4-flash</span>
      <span data-meta="budget">$0.00/$1.00</span>
    </>
  );

  it('sits under the subtitle on two panes with a rule between items, like the desktop hero', () => {
    inTwoPane(<ScreenHeader title="doc" subtitle="PROFILE · SETTINGS" meta={meta} />);
    expect(document.querySelectorAll('[data-meta]').length).toBe(2);
    expect(document.querySelectorAll('[testid="meta-sep"]').length).toBe(1);
  });

  it('stays out of the phone header', () => {
    render(<ScreenHeader title="doc" subtitle="PROFILE · SETTINGS" meta={meta} />);
    expect(document.querySelectorAll('[data-meta]').length).toBe(0);
  });
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

  it('moves the back control to the right of a drilled screen in two-pane mode, like the desktop hero', () => {
    h.pathname = '/profile/doc/settings';
    const onBack = vi.fn();
    inTwoPane(<ScreenHeader title="Settings" onBack={onBack} />);
    expect(screen.queryByText('back')).toBeNull();
    const arrow = screen.getByText('arrow-left');
    arrow.closest('button').click();
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('drops the chevron without an onBack handler', () => {
    render(<ScreenHeader title="Outputs" />);
    expect(screen.queryByText('back')).toBeNull();
  });
});
