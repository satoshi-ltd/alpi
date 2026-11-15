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

vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 0, bottom: 0 }) }));
vi.mock('../components/Glyph', () => ({ Glyph: () => React.createElement('span') }));
vi.mock('../components/Fold', () => ({ Fold: () => React.createElement('span') }));
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

  it('sets a settings label at the 15 pt ui rung and its description at 14 pt sans', () => {
    render(<Row label="Connections" value="alpi-casa" helper="two paired" onPress={() => {}} />);
    expect(sizeOf('Connections')).toBe(15);
    expect(fontOf('Connections')).toBe('sans-medium');
    expect(sizeOf('two paired')).toBe(14);
    expect(fontOf('two paired')).toBe('sans');
  });

  it('sets a row value at md, the ui rung', () => {
    render(<Row label="Connections" value="alpi-casa" onPress={() => {}} />);
    expect(sizeOf('alpi-casa')).toBe(fontSizes.md);
  });

  it('sets a section label at 14 pt sans medium in sentence case, never uppercase mono or tracked', () => {
    render(<Eyebrow>Connection</Eyebrow>);
    const node = screen.getByText('Connection');
    expect(Number(node.getAttribute('data-size'))).toBe(14);
    expect(node.getAttribute('data-font')).toBe('sans-medium');
    expect(node.getAttribute('data-transform')).toBeNull();
    expect(node.getAttribute('data-track')).toBeNull();
  });

  it('routes every section header through that one label', () => {
    render(<SectionHeader>Servers</SectionHeader>);
    expect(sizeOf('Servers')).toBe(fontSizes.sm);
    expect(fontOf('Servers')).toBe('sans-medium');
  });
});

describe('the phone → tablet step', () => {
  it('keeps the chat title at nav-bar xl on the tablet, so an unfolded phone still reads like a phone', () => {
    pane(false, <ChatHeader kind="workgroup" title="#alpha" />);
    expect(sizeOf('#alpha')).toBe(fontSizes.xl);
    cleanup();
    pane(true, <ChatHeader kind="workgroup" title="#alpha" />);
    expect(sizeOf('#alpha')).toBe(fontSizes.xl);
  });

  it('never tracks the chat title: no pane mode promotes it to a hero', () => {
    pane(true, <ChatHeader kind="workgroup" title="#alpha" />);
    expect(Number(screen.getByText('#alpha').getAttribute('data-track'))).toBe(0);
    cleanup();
    pane(false, <ChatHeader kind="workgroup" title="#alpha" />);
    expect(Number(screen.getByText('#alpha').getAttribute('data-track'))).toBe(0);
  });

  it('sets the roster name at the 15 pt ui rung on both panes and keeps the timestamp', () => {
    pane(false, <InboxRow item={ITEM} />);
    const phoneName = sizeOf('scout');
    const phoneTs = sizeOf('4m');
    cleanup();
    pane(true, <InboxRow item={ITEM} />);
    expect(phoneName).toBe(fontSizes.md);
    expect(sizeOf('scout')).toBe(fontSizes.md);
    expect(sizeOf('4m')).toBe(phoneTs);
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
