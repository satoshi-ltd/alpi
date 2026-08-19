import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => {
  const stack = ['/'];
  const top = () => stack[stack.length - 1];
  return {
    stack,
    top,
    seed: (entries) => { stack.length = 0; stack.push(...entries); },
    router: {
      push: (href) => { stack.push(String(href)); },
      replace: (href) => { stack[stack.length - 1] = String(href); },
      back: () => { if (stack.length > 1) stack.pop(); },
      canGoBack: () => stack.length > 1,
    },
    call: vi.fn(async () => ({})),
    profile: null,
  };
});

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement(
      'div',
      { ...p, ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}) },
      children,
    );
  const Text = ({ children, style, numberOfLines, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, onLongPress, style, hitSlop, accessibilityLabel, accessibilityRole, android_ripple, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, onContextMenu: onLongPress, 'aria-label': accessibilityLabel, ...p },
      children instanceof Function ? children({ pressed: false }) : children,
    );
  return {
    View,
    Text,
    Pressable,
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'spinner' }),
    FlatList: () => null,
    KeyboardAvoidingView: ({ children }) => React.createElement('div', {}, children),
    ScrollView: ({ children, ...p }) => React.createElement('div', {}, children),
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('expo-router', () => ({
  usePathname: () => h.top(),
  useRouter: () => h.router,
  useLocalSearchParams: () => ({ id: 'doc' }),
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      bg: '#fff', bgPane: '#fff', bgInput: '#f1f3f5', line: '#eee', line2: '#ddd',
      selected: '#eaeaea', hover: '#f4f4f4',
      ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999',
      accent: '#c90', danger: '#c00', warning: '#dd0', success: '#0a0',
    },
    fonts: {
      sans: { regular: 'r', medium: 'm', semibold: 's', bold: 'b' },
      mono: 'mono', monoMedium: 'monoMedium', monoSemibold: 'monoSemibold',
    },
    fontSizes: { xxs: 9, xs: 11, sm: 12, base: 13, md: 14, lg: 15, xl: 18, '2xl': 22, display: 28 },
    lineHeights: { tight: 1, cozy: 1.3, normal: 1.5, relaxed: 1.65 },
    mobile: { tap: 44, inputH: 44 },
    alpha: { muted: 0.55 },
  }),
}));

vi.mock('../src/components/ActionSheet', () => ({ ActionSheet: () => null }));
vi.mock('../src/components/AlpiMark', () => ({ AlpiMark: () => null }));
vi.mock('../src/components/Banner', () => ({ Banner: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/components/Button', () => ({ Button: ({ title }) => React.createElement('button', { type: 'button' }, title) }));
vi.mock('../src/components/Diamond', () => ({ Diamond: () => null }));
vi.mock('../src/components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../src/components/Meter', () => ({ Meter: () => null }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));

vi.mock('../src/features/chat/Bubble', () => ({ ProfileAssistantMessage: () => null, ProfileUserMessage: () => null }));
vi.mock('../src/features/chat/ChatSkeleton', () => ({ ChatSkeleton: () => null }));
vi.mock('../src/features/chat/Composer', () => ({ Composer: () => null }));
vi.mock('../src/features/chat/MessageActionsSheet', () => ({ MessageActionsSheet: () => null }));
vi.mock('../src/features/chat/Reasoning', () => ({ Reasoning: () => null }));
vi.mock('../src/features/chat/SoundWave', () => ({ SoundWave: () => null }));
vi.mock('../src/features/chat/ToolCallRow', () => ({ ToolModule: () => null }));
vi.mock('../src/features/sheets/SessionsSheet', () => ({ SessionsSheet: () => null }));
vi.mock('../src/features/aln/deeplink', () => ({ isForeignConnection: () => false }));

vi.mock('../src/hooks/useActiveRole', () => ({ useCanAdminEarly: () => true }));
vi.mock('../src/hooks/useChatSend', () => ({
  useChatSend: () => ({ send: vi.fn(), isSending: () => false, pendingTurn: null, isStreaming: false }),
}));
vi.mock('../src/hooks/useDaemonData', () => ({
  useProfileSummaries: () => ({ data: { profiles: h.profile ? [h.profile] : [] }, loading: false, refresh: vi.fn(async () => {}) }),
  useSessionsList: () => ({ data: { sessions: [] }, loading: false, refresh: vi.fn(async () => {}) }),
}));
vi.mock('../src/hooks/useDebouncedCallback', () => ({ useDebouncedCallback: (fn) => fn }));
vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/hooks/useSessionTranscript', () => ({
  useSessionTranscript: () => ({
    data: { turns: [], last_ctx_tokens: 0 },
    loading: false,
    turnsOffset: 0,
    inFlight: false,
    hasMore: false,
    loadOlder: vi.fn(),
    refresh: vi.fn(async () => {}),
  }),
}));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({
    endpoint: { id: 'c1', name: 'casa', url: 'http://casa' },
    activeId: 'c1',
    call: h.call,
    probeState: new Map([['c1', 'online']]),
  }),
}));
vi.mock('../src/lib/readAloud', () => ({ enqueueReadAloud: vi.fn() }));
vi.mock('../src/lib/readState', () => ({ markProfileRead: vi.fn() }));
vi.mock('../src/features/settings/SettingsBody', () => ({ SettingsBody: () => null }));

import ProfileChat from '../app/chat/[id].jsx';
import SettingsScreen from '../app/settings.jsx';
import { openVerb } from '../src/lib/panes';
import { PaneContext } from '../src/nav/PaneContext';

const TWO_PANE = { twoPane: true, side: 'detail' };

function paneIn(twoPane, node) {
  return twoPane ? <PaneContext.Provider value={TWO_PANE}>{node}</PaneContext.Provider> : node;
}

function screenIn(twoPane) {
  return paneIn(twoPane, <ProfileChat />);
}

function settingsIn(twoPane) {
  return paneIn(twoPane, <SettingsScreen />);
}

function open(twoPane, path) {
  h.router[openVerb({ twoPane, pathname: h.top() })](path);
}

function chevron() {
  return screen.queryByLabelText('Back');
}

function screenHeaderChevron() {
  return document.querySelector('[data-icon="back"]')?.parentElement ?? null;
}

beforeEach(() => {
  h.seed(['/']);
  h.call.mockClear().mockResolvedValue({});
  h.profile = { name: 'doc', accent: '#abc123', model: 'anthropic/claude-opus-5', provider_keys: ['anthropic'], paused: false };
});

describe('fold from two-pane to single-pane', () => {
  it('leaves a route back to the roster after the sidebar replaced it away', () => {
    open(true, '/chat/doc');
    expect(h.stack).toEqual(['/chat/doc']);

    const { rerender } = render(screenIn(true));
    expect(chevron()).toBeNull();

    rerender(screenIn(false));
    expect(chevron()).toBeTruthy();

    fireEvent.click(chevron());
    expect(h.top()).toBe('/');
  });

  it('reaches the roster from a shell destination the sidebar footer replaced away', () => {
    open(true, '/settings');
    expect(h.stack).toEqual(['/settings']);

    const { rerender } = render(settingsIn(true));
    expect(screenHeaderChevron()).toBeNull();

    rerender(settingsIn(false));
    fireEvent.click(screenHeaderChevron());
    expect(h.top()).toBe('/');
  });

  it('reaches the roster after the sidebar replaced through a whole row of subjects', () => {
    for (const path of ['/chat/doc', '/wg/alpha', '/chat/agora', '/chat/doc']) open(true, path);
    expect(h.stack).toEqual(['/chat/doc']);

    const { rerender } = render(screenIn(true));
    rerender(screenIn(false));
    fireEvent.click(chevron());
    expect(h.stack).toEqual(['/']);
  });
});

describe('unfold from single-pane to two-pane', () => {
  it('offers no back to a roster the sidebar already shows', () => {
    open(false, '/chat/doc');
    expect(h.stack).toEqual(['/', '/chat/doc']);

    const { rerender } = render(screenIn(false));
    expect(chevron()).toBeTruthy();

    rerender(screenIn(true));
    expect(chevron()).toBeNull();
  });

  it('still reaches the roster when the device folds back again', () => {
    open(false, '/chat/doc');
    const { rerender } = render(screenIn(false));
    rerender(screenIn(true));
    rerender(screenIn(false));

    fireEvent.click(chevron());
    expect(h.top()).toBe('/');
  });
});

describe('flipping back and forth under the user', () => {
  it('keeps the stack flat and back working however many times the device folds', () => {
    open(true, '/chat/doc');
    const { rerender } = render(screenIn(true));

    for (const twoPane of [false, true, false, true, true, false]) {
      rerender(screenIn(twoPane));
      expect(h.stack).toEqual(['/chat/doc']);
      expect(!!chevron()).toBe(!twoPane);
    }

    fireEvent.click(chevron());
    expect(h.stack).toEqual(['/']);
  });

  it('never offers a chevron that moves nothing', () => {
    for (const [twoPane, seed] of [[false, ['/chat/doc']], [false, ['/', '/chat/doc']], [true, ['/', '/chat/doc']]]) {
      h.seed(seed);
      const view = render(screenIn(twoPane));
      const before = [...h.stack];
      if (chevron()) {
        fireEvent.click(chevron());
        expect(h.stack).not.toEqual(before);
      }
      view.unmount();
    }
  });
});
