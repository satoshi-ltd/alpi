import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  call: vi.fn(async () => ({})),
  profile: null,
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, onLayout, ...p }) =>
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
    ScrollView: ({ children }) => React.createElement('div', {}, children),
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    Dimensions: { get: () => ({ height: 852, width: 393 }) },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('expo-router', () => ({
  usePathname: () => '/chat/doc',
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), canGoBack: () => true }),
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
// A stateful stand-in: a remount, not the real Composer, is what this test guards against.
vi.mock('../src/features/chat/Composer', () => ({
  Composer: () => {
    const [text, setText] = React.useState('');
    return React.createElement('input', {
      'aria-label': 'composer',
      value: text,
      onChange: (e) => setText(e.target.value),
    });
  },
}));
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

import ProfileChat from '../app/chat/[id].jsx';
import { PaneContext } from '../src/nav/PaneContext';

const ONE_PANE = { twoPane: false, side: 'full', sidebarOpen: true, toggleSidebar: () => {} };
const TWO_PANE = { twoPane: true, side: 'detail', sidebarOpen: false, toggleSidebar: () => {} };

// The provider stays in place and only its value flips, as PaneShell does on a real fold.
function screenIn(twoPane) {
  return (
    <PaneContext.Provider value={twoPane ? TWO_PANE : ONE_PANE}>
      <ProfileChat />
    </PaneContext.Provider>
  );
}

function composer() {
  return screen.getByLabelText('composer');
}

beforeEach(() => {
  h.call.mockClear().mockResolvedValue({});
  h.profile = { name: 'doc', accent: '#abc123', model: 'anthropic/claude-opus-5', provider_keys: ['anthropic'], paused: false };
});

describe('composer text across a fold', () => {
  it('survives opening the phone', () => {
    const { rerender } = render(screenIn(false));
    fireEvent.change(composer(), { target: { value: 'hola' } });
    rerender(screenIn(true));
    expect(composer().value).toBe('hola');
  });

  it('survives closing it again', () => {
    const { rerender } = render(screenIn(true));
    fireEvent.change(composer(), { target: { value: 'still here' } });
    rerender(screenIn(false));
    expect(composer().value).toBe('still here');
  });
});
