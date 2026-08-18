import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import { fontSizes, lineHeights, tracking } from './tokens';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  pick: (style, key) => [style].flat(Infinity).filter(Boolean).reduce((v, s) => s?.[key] ?? v, null),
}));

vi.mock('react-native', () => {
  const attrs = ({ style, contentContainerStyle, accessibilityLabel, numberOfLines, ellipsizeMode, ...rest }) => ({
    ...rest,
    ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
    'data-size': h.pick(style, 'fontSize'),
    'data-font': h.pick(style, 'fontFamily'),
    'data-track': h.pick(style, 'letterSpacing'),
    'data-transform': h.pick(style, 'textTransform'),
  });
  const View = ({ children, ...p }) => React.createElement('div', attrs(p), children);
  const Text = ({ children, ...p }) => React.createElement('span', attrs(p), children);
  const Pressable = ({ children, onPress, hitSlop, android_ripple, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...attrs(p) },
      children instanceof Function ? children({ pressed: false }) : children);
  return { View, Text, Pressable, ScrollView: View, StyleSheet: { create: (s) => s } };
});

vi.mock('expo-router', () => ({
  usePathname: () => '/settings/deep',
  useRouter: () => ({ canGoBack: () => true }),
}));

vi.mock('../components/Glyph', () => ({ Glyph: () => React.createElement('span') }));
vi.mock('../components/Diamond', () => ({ Diamond: () => React.createElement('span') }));
vi.mock('../features/inbox/Pip', () => ({ Pip: () => null }));

vi.mock('./ThemeContext', () => ({
  useTheme: () => ({
    fontSizes,
    lineHeights,
    colors: {
      accent: '#c9a227', bg: '#fff', bgPane: '#fff', danger: '#f00', hover: '#eee',
      ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', line: '#ddd', selected: '#eee',
    },
    fonts: {
      sans: { regular: 'sans', medium: 'sans-medium', semibold: 'sans-semibold', bold: 'sans-bold' },
      mono: 'mono', monoMedium: 'mono-medium', monoSemibold: 'mono-semibold',
    },
    alpha: { muted: 0.55 },
    mobile: { tap: 44 },
  }),
}));

const { Eyebrow } = await import('../components/Eyebrow');
const { Row, SectionHeader } = await import('../components/Row');
const { ScreenHeader } = await import('../components/ScreenHeader');
const { ChatHeader } = await import('../features/chat/ChatHeader');
const { InboxRow } = await import('../features/inbox/InboxRow');
const { PaneContext } = await import('../nav/PaneContext');

const sizeOf = (text) => Number(screen.getByText(text).getAttribute('data-size'));
const fontOf = (text) => screen.getByText(text).getAttribute('data-font');

function pane(twoPane, node) {
  return render(
    <PaneContext.Provider value={{ twoPane, side: twoPane ? 'detail' : 'full' }}>{node}</PaneContext.Provider>,
  );
}

const ITEM = { kind: 'profile', id: 'scout', label: 'scout', preview: 'ready when you are', ts: '4m' };

describe('one token per typographic role', () => {
  it('sets a screen title at xl — the step desktop reserves for dialog headings', () => {
    render(<ScreenHeader title="Providers" />);
    expect(sizeOf('Providers')).toBe(fontSizes.xl);
    expect(fontOf('Providers')).toBe('sans-semibold');
  });

  it('sets a row title at lg, the mobile body workhorse', () => {
    render(<Row label="Connections" value="alpi-casa" helper="two paired" onPress={() => {}} />);
    expect(sizeOf('Connections')).toBe(fontSizes.lg);
  });

  it('sets a body line at md, one step under the row title it sits beside', () => {
    render(<Row label="Connections" value="alpi-casa" onPress={() => {}} />);
    expect(sizeOf('alpi-casa')).toBe(fontSizes.md);
  });

  it('sets an eyebrow at xs, mono medium, uppercase, on desktop .06em tracking', () => {
    render(<Eyebrow>connection</Eyebrow>);
    const node = screen.getByText('connection');
    expect(Number(node.getAttribute('data-size'))).toBe(fontSizes.xs);
    expect(node.getAttribute('data-font')).toBe('mono-medium');
    expect(node.getAttribute('data-transform')).toBe('uppercase');
    expect(Number(node.getAttribute('data-track'))).toBeCloseTo(fontSizes.xs * tracking.wide, 5);
  });

  it('routes every section header through that one eyebrow', () => {
    render(<SectionHeader>servers</SectionHeader>);
    expect(sizeOf('servers')).toBe(fontSizes.xs);
    expect(fontOf('servers')).toBe('mono-medium');
  });
});

describe('the phone → tablet step', () => {
  it('lifts the chat title from nav-bar xl to desktop hero display', () => {
    pane(false, <ChatHeader kind="workgroup" title="#alpha" />);
    expect(sizeOf('#alpha')).toBe(fontSizes.xl);
    cleanup();
    pane(true, <ChatHeader kind="workgroup" title="#alpha" />);
    expect(sizeOf('#alpha')).toBe(fontSizes.display);
  });

  it('tracks the hero title tighter, and only the hero title', () => {
    pane(true, <ChatHeader kind="workgroup" title="#alpha" />);
    expect(Number(screen.getByText('#alpha').getAttribute('data-track')))
      .toBeCloseTo(fontSizes.display * tracking.tight, 5);
    cleanup();
    pane(false, <ChatHeader kind="workgroup" title="#alpha" />);
    expect(Number(screen.getByText('#alpha').getAttribute('data-track'))).toBe(0);
  });

  it('leaves every other role at one size, so the sidebar does not drift with the header', () => {
    pane(false, <InboxRow item={ITEM} />);
    const phoneName = sizeOf('scout');
    const phoneTs = sizeOf('4m');
    cleanup();
    pane(true, <InboxRow item={ITEM} />);
    expect(sizeOf('scout')).toBe(phoneName);
    expect(sizeOf('4m')).toBe(phoneTs);
    expect(phoneName).toBe(fontSizes.lg);
  });

  it('keeps the chat meta line at one size in both modes', () => {
    pane(false, <ChatHeader kind="workgroup" title="#alpha" meta="4 members" />);
    const phone = sizeOf('4 members');
    cleanup();
    pane(true, <ChatHeader kind="workgroup" title="#alpha" meta="4 members" />);
    expect(sizeOf('4 members')).toBe(phone);
    expect(phone).toBe(fontSizes.xs);
  });
});
