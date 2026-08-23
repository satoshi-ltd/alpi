import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  params: { id: 'agora' },
  flatStyle: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) =>
    React.createElement('div', { ...p, 'data-style': JSON.stringify(h.flatStyle(style)) }, children);
  const Text = ({ children, style, numberOfLines, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, hitSlop, style, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...p }, children);
  const FlatList = ({ data, renderItem, keyExtractor, contentContainerStyle }) =>
    React.createElement(
      'div',
      { 'data-list': 'true', 'data-style': JSON.stringify(h.flatStyle(contentContainerStyle)) },
      (data ?? []).map((item, index) =>
        React.createElement('div', { key: keyExtractor ? keyExtractor(item, index) : index }, renderItem({ item, index })),
      ),
    );
  return {
    View,
    Text,
    Pressable,
    FlatList,
    KeyboardAvoidingView: ({ children }) => React.createElement('div', { 'data-kav': 'true' }, children),
    ActivityIndicator: () => React.createElement('span', { 'data-spinner': 'true' }),
    Platform: { OS: 'ios', select: (sel) => sel?.ios ?? sel?.default },
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('expo-router', () => ({
  useLocalSearchParams: () => h.params,
  usePathname: () => '/',
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn() }),
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

vi.mock('../src/components/KeyboardPane', () => ({
  KeyboardPane: ({ children }) => React.createElement('div', { 'data-kav': 'true' }, children),
}));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      bg: '#fff', bgPane: '#fff', bgInput: '#eee', ink: '#000', ink2: '#333', ink3: '#666',
      line: '#eee', selected: '#eee', danger: '#f00', warning: '#fa0', success: '#0a0',
    },
    fonts: {
      sans: { regular: 'Inter_400Regular', medium: 'Inter_500Medium', semibold: 'Inter_600SemiBold' },
      mono: 'JetBrainsMono_400Regular', monoMedium: 'JetBrainsMono_500Medium', monoSemibold: 'JetBrainsMono_600SemiBold',
    },
    fontSizes: { xxs: 9, xs: 11, sm: 12, md: 14, lg: 15, xl: 18, '2xl': 22 },
    lineHeights: { normal: 1.5 },
  }),
}));

vi.mock('../src/components/ActionSheet', () => ({ ActionSheet: () => null }));
vi.mock('../src/components/AlpiMark', () => ({ AlpiMark: () => React.createElement('span', {}) }));
vi.mock('../src/components/Button', () => ({ Button: ({ title }) => React.createElement('button', { type: 'button' }, title) }));
vi.mock('../src/components/Diamond', () => ({ Diamond: () => React.createElement('span', {}) }));
vi.mock('../src/components/Dot', () => ({ Dot: () => React.createElement('span', {}) }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../src/features/chat/Bubble', () => ({
  ProfileUserMessage: ({ text }) => React.createElement('span', {}, text),
  ProfileAssistantMessage: ({ text }) => React.createElement('span', {}, text),
  WorkgroupMessage: ({ body }) => React.createElement('span', {}, body),
}));
vi.mock('../src/features/chat/ChatHeader', () => ({
  ChatHeader: ({ title }) => React.createElement('h1', {}, title),
  headerMenuActions: () => [],
}));
vi.mock('../src/features/chat/ChatSkeleton', () => ({ ChatSkeleton: () => React.createElement('span', { 'data-skeleton': 'true' }) }));
vi.mock('../src/features/chat/Composer', () => ({ Composer: () => React.createElement('span', { 'data-composer': 'true' }) }));
vi.mock('../src/features/chat/MarkerCard', () => ({ MarkerCard: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/features/chat/MessageActionsSheet', () => ({ MessageActionsSheet: () => null }));
vi.mock('../src/features/chat/PipelineStrip', () => ({ PipelineStrip: () => null }));
vi.mock('../src/features/chat/Reasoning', () => ({ Reasoning: () => null }));
vi.mock('../src/features/chat/SoundWave', () => ({ SoundWave: () => null }));
vi.mock('../src/features/chat/ToolCallRow', () => ({ ToolModule: () => null }));
vi.mock('../src/features/sheets/SessionsSheet', () => ({ SessionsSheet: () => null }));
vi.mock('../src/features/sheets/RunsSheet', () => ({ RunsSheet: () => null }));
vi.mock('../src/features/sheets/TasksSheet', () => ({ TasksSheet: () => null }));
vi.mock('../src/features/aln/deeplink', () => ({ isForeignConnection: () => false }));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({ activeId: 'e1', endpoint: { id: 'e1' }, call: vi.fn(() => new Promise(() => {})) }),
}));
vi.mock('../src/lib/readAloud', () => ({ enqueueReadAloud: vi.fn() }));
vi.mock('../src/lib/readState', () => ({ markProfileRead: vi.fn(), markWorkgroupRead: vi.fn() }));
vi.mock('../src/hooks/useActiveRole', () => ({ useCanAdminEarly: () => false }));
vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/hooks/useChatSend', () => ({
  useChatSend: () => ({ send: vi.fn(), isSending: () => false, pendingTurn: null, isStreaming: false }),
}));
vi.mock('../src/hooks/useSessionTranscript', () => ({
  isMissingSession: () => false,
  useSessionTranscript: () => ({
    data: { turns: [{ user: 'ping', assistant: 'pong', at: 0 }] },
    turnsOffset: 0,
    inFlight: false,
    hasMore: false,
    loading: false,
    settled: true,
    loadOlder: vi.fn(),
    refresh: vi.fn(),
  }),
}));
vi.mock('../src/hooks/useDaemonData', () => ({
  useProfileSummaries: () => ({
    data: {
      profiles: [{
        name: 'agora',
        accent: '#0af0af',
        model: 'openrouter/deepseek-v4-flash',
        pubkey_b64: 'k-agora',
        latest_session: { kind: 'chat', id: 's1', updated_at: 10 },
      }],
    },
    loading: false,
    refresh: vi.fn(),
  }),
  useSessionsList: () => ({ data: { sessions: [{ id: 's1', kind: 'chat' }] }, loading: false, refresh: vi.fn() }),
  useWorkgroups: () => ({
    data: { workgroups: [{ id: 'alpha', name: '#alpha', hub_id: 'scout', profile: 'agora', mtime: 5, members: 2 }] },
    loading: false,
    refresh: vi.fn(),
  }),
  useWorkgroupMembers: () => ({ data: { members: ['scout', 'agora'] }, loading: false, refresh: vi.fn() }),
  useWorkgroupTasks: () => ({ data: {}, loading: false, refresh: vi.fn() }),
  useWorkgroupTranscript: () => ({
    data: { posts: [{ seq: 1, from: '@scout', from_pubkey: 'k-scout', body: 'status?' }] },
    loading: false,
    refresh: vi.fn(),
  }),
}));

import { PaneContext } from '../src/nav/PaneContext';
import ProfileChat from '../app/chat/[id].jsx';
import WorkgroupChat from '../app/wg/[id].jsx';

function mount(node, twoPane) {
  if (!twoPane) return render(node);
  return render(
    <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>{node}</PaneContext.Provider>,
  );
}

function listStyle(container) {
  return JSON.parse(container.querySelector('[data-list]').getAttribute('data-style'));
}

function composerParentStyle(container) {
  return JSON.parse(container.querySelector('[data-composer]').parentElement.getAttribute('data-style') || '{}');
}

const SCREENS = [
  ['profile chat', () => <ProfileChat />, { id: 'agora' }, 'pong'],
  ['workgroup', () => <WorkgroupChat />, { id: 'alpha' }, 'status?'],
];

describe.each(SCREENS)('%s content column', (_name, Screen, params, sample) => {
  it('caps and centres the transcript and the composer in two-pane mode', () => {
    h.params = params;
    const { container } = mount(Screen(), true);
    expect(screen.getByText(sample)).toBeTruthy();
    expect(listStyle(container)).toMatchObject({ alignSelf: 'center', width: '100%', maxWidth: 720 });
    expect(composerParentStyle(container)).toMatchObject({ alignSelf: 'center', width: '100%', maxWidth: 720 });
  });

  it('leaves the row padding as the only inset — the column adds none', () => {
    h.params = params;
    const { container } = mount(Screen(), true);
    expect(listStyle(container).paddingHorizontal).toBeUndefined();
    expect(composerParentStyle(container).paddingHorizontal).toBeUndefined();
  });

  it('leaves the single-pane tree uncapped and unwrapped', () => {
    h.params = params;
    const { container } = mount(Screen(), false);
    expect(screen.getByText(sample)).toBeTruthy();
    expect(listStyle(container).paddingHorizontal).toBeUndefined();
    expect(listStyle(container).maxWidth).toBeUndefined();
    expect(container.querySelector('[data-composer]').parentElement.getAttribute('data-kav')).toBe('true');
    expect([...container.querySelectorAll('[data-style]')].some(
      (node) => JSON.parse(node.getAttribute('data-style')).maxWidth === 720,
    )).toBe(false);
  });
});
