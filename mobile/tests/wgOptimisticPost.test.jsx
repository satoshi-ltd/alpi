import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  call: vi.fn(async () => ({})),
  refreshTranscript: vi.fn(),
  refreshTasks: vi.fn(async () => {}),
  eventHandler: null,
  posts: [],
  wg: null,
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement(
      'div',
      { ...p, ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}) },
      children,
    );
  const Text = ({ children, style, numberOfLines, accessibilityRole, ...p }) =>
    React.createElement('span', p, children);
  const Pressable = ({ children, onPress, onLongPress, style, hitSlop, accessibilityLabel, android_ripple, ...p }) =>
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
    FlatList: ({ data = [], renderItem, keyExtractor }) =>
      React.createElement(
        'div',
        { 'data-list': 'posts' },
        data.map((item, index) =>
          React.createElement(
            'div',
            { key: keyExtractor ? keyExtractor(item, index) : index },
            renderItem({ item, index }),
          )),
      ),
    Dimensions: { get: () => ({ height: 800, width: 400 }) },
    KeyboardAvoidingView: ({ children }) => React.createElement('div', {}, children),
    ScrollView: ({ children, horizontal, style, contentContainerStyle, ...p }) =>
      React.createElement('div', { ...p }, children),
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('expo-router', () => ({
  usePathname: () => '/wg/alpha',
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), canGoBack: () => true }),
  useLocalSearchParams: () => ({ id: 'alpha' }),
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
vi.mock('../src/components/Banner', () => ({ Banner: ({ kind, children }) => React.createElement('div', { 'data-banner': kind }, children) }));
vi.mock('../src/components/Diamond', () => ({ Diamond: () => null }));
vi.mock('../src/components/Dot', () => ({ Dot: () => null }));
vi.mock('../src/components/Icon', () => ({ Icon: () => null }));
vi.mock('../src/components/Meter', () => ({ Meter: () => null }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));

vi.mock('../src/features/chat/Bubble', () => ({
  WorkgroupMessage: ({ body }) => React.createElement('span', { 'data-post': 'true' }, body),
}));
vi.mock('../src/features/chat/ChatSkeleton', () => ({ ChatSkeleton: () => React.createElement('div', { 'data-skeleton': 'wg' }) }));
vi.mock('../src/features/chat/Composer', () => ({
  Composer: ({ onSend, disabled }) =>
    React.createElement(
      'button',
      { type: 'button', 'data-send': 'true', disabled: !!disabled, onClick: () => onSend('hola') },
      'send',
    ),
}));
vi.mock('../src/features/chat/MarkerCard', () => ({ MarkerCard: () => null }));
vi.mock('../src/features/chat/MessageActionsSheet', () => ({ MessageActionsSheet: () => null }));
vi.mock('../src/features/chat/PipelineStrip', () => ({ PipelineStrip: () => null }));
vi.mock('../src/features/chat/SoundWave', () => ({ SoundWave: () => null }));
vi.mock('../src/features/sheets/TasksSheet', () => ({ TasksSheet: () => null }));
vi.mock('../src/features/aln/deeplink', () => ({ isForeignConnection: () => false }));

vi.mock('../src/hooks/useActiveRole', () => ({ useCanAdminEarly: () => true }));
vi.mock('../src/hooks/useDaemonData', () => ({
  useProfileSummaries: () => ({ data: { profiles: [] }, loading: false, refresh: vi.fn() }),
  useWorkgroups: () => ({ data: { workgroups: h.wg ? [h.wg] : [] }, loading: false, refresh: vi.fn() }),
  useWorkgroupMembers: () => ({ data: { members: [] }, loading: false, refresh: vi.fn() }),
  useWorkgroupTasks: () => ({ data: null, loading: false, refresh: h.refreshTasks }),
  useWorkgroupTranscript: () => ({
    data: { posts: h.posts },
    loading: false,
    refresh: h.refreshTranscript,
  }),
}));
vi.mock('../src/hooks/useDebouncedCallback', () => ({ useDebouncedCallback: (fn) => fn }));
vi.mock('../src/hooks/useEvents', () => ({
  useEventEffect: (_kinds, fn) => { h.eventHandler = fn; },
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
vi.mock('../src/lib/readState', () => ({ markWorkgroupRead: vi.fn() }));

import WorkgroupChat from '../app/wg/[id].jsx';

const WG = {
  id: 'alpha',
  name: 'alpha',
  profile: 'doc',
  hub_id: 'doc',
  is_hub: true,
  paused: false,
  auto_read: false,
  mtime: 1,
};

const LANDED = { seq: 1, from: '@doc', from_pubkey: 'local:doc', body: 'hola' };

function postTexts() {
  return [...document.querySelectorAll('[data-post]')].map((el) => el.textContent);
}

function send() {
  fireEvent.click(document.querySelector('[data-send]'));
}

beforeEach(() => {
  h.call.mockReset().mockResolvedValue({});
  h.refreshTasks.mockClear();
  h.eventHandler = null;
  h.posts = [];
  h.wg = { ...WG };
  h.refreshTranscript = vi.fn(async () => ({ posts: h.posts }));
});

describe('a posted workgroup message never leaves the thread', () => {
  it('keeps the post visible when the refresh that follows it comes back without it', async () => {
    render(<WorkgroupChat />);
    await act(async () => { send(); });
    expect(postTexts()).toEqual(['hola']);
  });

  it('keeps the post visible when a wg.post event fires while the post refresh is still in flight', async () => {
    h.refreshTranscript = vi.fn(() => new Promise(() => {}));
    render(<WorkgroupChat />);
    await act(async () => { send(); });
    expect(postTexts()).toEqual(['hola']);

    await act(async () => { h.eventHandler({ data: { wg_id: 'alpha' } }); });
    expect(postTexts()).toEqual(['hola']);
  });

  it('shows exactly one copy once the transcript carries the post', async () => {
    render(<WorkgroupChat />);
    await act(async () => { send(); });

    h.posts = [LANDED];
    await act(async () => { h.eventHandler({ data: { wg_id: 'alpha' } }); });
    expect(postTexts()).toEqual(['hola']);
  });

  it('keeps the failed post on screen with its error', async () => {
    h.call.mockRejectedValue(new Error('offline'));
    render(<WorkgroupChat />);
    await act(async () => { send(); });
    expect(postTexts()).toEqual(['hola']);
    expect(document.body.textContent).toMatch(/offline/);
  });
});
