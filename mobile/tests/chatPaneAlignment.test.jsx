import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  flatStyle: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
}));

vi.mock('react-native', () => {
  const flat = (style) => JSON.stringify(h.flatStyle(style instanceof Function ? style({ pressed: false }) : style));
  const View = ({ children, style }) => React.createElement('div', { 'data-style': flat(style) }, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-style': flat(style) }, children);
  const Pressable = ({ children, style }) =>
    React.createElement(
      'div',
      { 'data-style': flat(style) },
      children instanceof Function ? children({ pressed: false }) : children,
    );
  const ScrollView = ({ children, style, contentContainerStyle }) =>
    React.createElement(
      'div',
      { 'data-style': flat(style) },
      React.createElement('div', { 'data-style': flat(contentContainerStyle) }, children),
    );
  const TextInput = ({ style }) =>
    React.createElement('input', { 'data-input': 'true', 'data-style': flat(style), readOnly: true });
  return {
    View,
    Text,
    Pressable,
    ScrollView,
    TextInput,
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('expo-router', () => ({
  usePathname: () => '/chat/doc',
  useRouter: () => ({ canGoBack: () => true }),
}));

vi.mock('react-native-safe-area-context', () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

vi.mock('../src/theme/ThemeContext', async () => {
  const tokens = await import('../src/theme/tokens');
  return {
    useTheme: () => ({
      colors: tokens.palettes.light,
      fonts: tokens.fonts,
      fontSizes: tokens.fontSizes,
      lineHeights: tokens.lineHeights,
      mobile: tokens.mobile,
    }),
  };
});

vi.mock('../src/components/Diamond', () => ({ Diamond: () => React.createElement('span', {}) }));
vi.mock('../src/components/Icon', () => ({ Icon: () => React.createElement('span', {}) }));
vi.mock('../src/components/RichText', () => ({
  RichText: ({ children }) => React.createElement('span', { 'data-body': 'true' }, children),
}));
vi.mock('../src/features/chat/AttachmentCards', () => ({ AttachmentCards: () => React.createElement('span', {}) }));
vi.mock('../src/features/chat/MentionPopover', () => ({ MentionPopover: () => null }));

import { PANE_PAD_X } from '../src/lib/panes';
import { PaneContext } from '../src/nav/PaneContext';
import { space } from '../src/theme/tokens';
import { ProfileAssistantMessage, WorkgroupMessage } from '../src/features/chat/Bubble';
import { ChatHeader } from '../src/features/chat/ChatHeader';
import { Composer } from '../src/features/chat/Composer';
import { ConnHeader } from '../src/features/inbox/ConnHeader';

function mount(node, twoPane) {
  return render(
    <PaneContext.Provider value={{ twoPane, side: twoPane ? 'detail' : 'full' }}>{node}</PaneContext.Provider>,
  );
}

function rootStyle(container) {
  return JSON.parse(container.firstChild.getAttribute('data-style'));
}

function edge(el) {
  let total = 0;
  for (let node = el?.parentElement; node; node = node.parentElement) {
    const raw = node.getAttribute('data-style');
    if (!raw) continue;
    const style = JSON.parse(raw);
    total += style.paddingHorizontal ?? style.paddingLeft ?? 0;
  }
  return total;
}

const SURFACES = [
  [
    'header',
    () => <ChatHeader kind="workgroup" title="#alpha" />,
    (container) => [...container.querySelectorAll('span')].find((n) => n.textContent === '#alpha'),
  ],
  [
    'transcript',
    () => <ProfileAssistantMessage text="shipped" />,
    (container) => container.querySelector('[data-body]'),
  ],
  [
    'composer',
    () => <Composer placeholder="Message @doc…" />,
    (container) => container.querySelector('[data-input]'),
  ],
];

describe.each([['phone', false], ['two-pane', true]])('chat pane left edge on a %s', (_name, twoPane) => {
  it('starts header, transcript and composer on the very same inset', () => {
    const insets = SURFACES.map(([, node, pick]) => {
      const { container } = mount(node(), twoPane);
      const inset = edge(pick(container));
      cleanup();
      return inset;
    });
    expect(new Set(insets).size).toBe(1);
    expect(insets[0]).toBe(PANE_PAD_X);
  });

  it('puts the workgroup row on that inset too', () => {
    const { container } = mount(
      <WorkgroupMessage body="status?" speakerName="scout" speakerAccent="#0af0af" seq={7} />,
      twoPane,
    );
    expect(edge(container.querySelector('[data-body]').parentElement)).toBe(PANE_PAD_X);
  });
});

describe('chat pane top edge', () => {
  function chatHeaderTop(twoPane) {
    const { container, unmount } = mount(<ChatHeader kind="profile" title="doc" />, twoPane);
    const top = rootStyle(container).paddingTop;
    unmount();
    return top;
  }

  it('lands the two-pane title on the sidebar eyebrow line', () => {
    const { container, unmount } = mount(<ConnHeader name="casa" host="host.sock" />, true);
    const sidebarTop = rootStyle(container).paddingTop;
    unmount();
    expect(chatHeaderTop(true)).toBe(sidebarTop);
  });

  it('drops the desktop hero padding the tablet header used to carry', () => {
    expect(chatHeaderTop(true)).toBeLessThan(space.s11);
  });

  it('gives the phone the same trimmed top as the tablet', () => {
    expect(chatHeaderTop(false)).toBe(space.s2);
    expect(chatHeaderTop(false)).toBe(chatHeaderTop(true));
  });
});
