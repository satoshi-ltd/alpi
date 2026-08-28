import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  params: { id: 'doc' },
  handlers: {},
  events: [],
}));

function reply(method, params) {
  const handler = h.handlers[method];
  if (!handler) return Promise.resolve({});
  return Promise.resolve(handler(params));
}

function notFound() {
  const e = new Error('not-found');
  e.code = -32004;
  return e;
}

function deferred() {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
}

function watchFrames() {
  const frames = [];
  const observer = new MutationObserver(() => frames.push(document.body.textContent));
  observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true });
  return {
    stop: () => observer.disconnect(),
    sawText: (text) => frames.some((f) => f.includes(text)),
  };
}

async function settle() {
  for (let i = 0; i < 4; i += 1) {
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  }
}

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement('div', p, children);
  const Text = ({ children, style, numberOfLines, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, style, hitSlop, accessibilityLabel, android_ripple, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, ...p },
      children instanceof Function ? children({ pressed: false }) : children,
    );
  return {
    View,
    Text,
    Pressable,
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'spinner' }),
    FlatList: ({ data }) => React.createElement('div', { 'data-list': String(data.length) }),
    KeyboardAvoidingView: ({ children }) => React.createElement('div', {}, children),
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('expo-router', () => ({
  usePathname: () => '/',
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), canGoBack: () => true }),
  useLocalSearchParams: () => h.params,
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
vi.mock('../src/components/AlpiMark', () => ({
  AlpiMark: ({ color }) => React.createElement('span', { 'data-mark': color }),
}));
vi.mock('../src/components/Banner', () => ({ Banner: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/components/Button', () => ({ Button: ({ title }) => React.createElement('button', { type: 'button' }, title) }));
vi.mock('../src/components/Diamond', () => ({ Diamond: () => React.createElement('span', {}) }));
vi.mock('../src/components/Dot', () => ({ Dot: () => React.createElement('span', {}) }));
vi.mock('../src/components/Meter', () => ({ Meter: () => null }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));

vi.mock('../src/features/chat/Bubble', () => ({
  ProfileAssistantMessage: () => null,
  ProfileUserMessage: () => null,
  WorkgroupMessage: () => null,
}));
vi.mock('../src/features/chat/ChatHeader', () => ({
  ChatHeader: ({ title }) => React.createElement('h1', {}, title),
  headerMenuActions: () => [],
}));
vi.mock('../src/features/chat/ChatSkeleton', () => ({
  ChatSkeleton: ({ kind }) => React.createElement('div', { 'data-skeleton': kind }),
}));
vi.mock('../src/features/chat/Composer', () => ({
  Composer: ({ disabled, placeholder }) =>
    React.createElement('div', { 'data-composer': placeholder, 'data-disabled': String(!!disabled) }),
}));
vi.mock('../src/features/chat/MarkerCard', () => ({ MarkerCard: () => null }));
vi.mock('../src/features/chat/MessageActionsSheet', () => ({ MessageActionsSheet: () => null }));
vi.mock('../src/features/chat/PipelineStrip', () => ({ PipelineStrip: () => null }));
vi.mock('../src/features/chat/Reasoning', () => ({ Reasoning: () => null }));
vi.mock('../src/features/chat/SoundWave', () => ({ SoundWave: () => null }));
vi.mock('../src/features/chat/ToolCallRow', () => ({ ToolModule: () => null }));
vi.mock('../src/features/sheets/SessionsSheet', () => ({ SessionsSheet: () => null }));
vi.mock('../src/features/sheets/TasksSheet', () => ({ TasksSheet: () => null }));
vi.mock('../src/features/aln/deeplink', () => ({ isForeignConnection: () => false }));

vi.mock('../src/hooks/useActiveRole', () => ({ useCanAdminEarly: () => true }));
vi.mock('../src/hooks/useChatSend', () => ({
  useChatSend: () => ({ send: vi.fn(), isSending: () => false, pendingTurn: null, isStreaming: false }),
}));
vi.mock('../src/hooks/useDebouncedCallback', () => ({ useDebouncedCallback: (fn) => fn }));
vi.mock('../src/hooks/useEvents', () => ({
  useEventEffect: (names, fn) => { h.events.push({ names: [].concat(names), fn }); },
}));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({
    endpoint: { id: 'c1', name: 'casa', url: 'http://casa' },
    activeId: 'c1',
    call: reply,
    probeState: new Map([['c1', 'online']]),
  }),
}));
vi.mock('../src/lib/readAloud', () => ({ enqueueReadAloud: vi.fn() }));
vi.mock('../src/lib/readState', () => ({ markProfileRead: vi.fn(), markWorkgroupRead: vi.fn() }));

import ProfileChat from '../app/chat/[id].jsx';
import WorkgroupChat from '../app/wg/[id].jsx';
import { _resetDaemonDataCache } from '../src/hooks/useDaemonData';
import { _resetSessionTranscriptStore } from '../src/hooks/useSessionTranscript';

const DOC = {
  name: 'doc',
  accent: '#abc123',
  model: 'anthropic/claude-opus-5',
  provider_keys: ['anthropic'],
  paused: false,
};

const WG = { id: 'alpha', name: '#alpha', hub_id: 'scout', profile: 'agora', mtime: 5, members: 2 };

function skeleton() {
  return document.querySelector('[data-skeleton]');
}

function hasText(text) {
  return [...document.querySelectorAll('span')].some((el) => el.textContent === text);
}

async function emit(name, data) {
  const entry = [...h.events].reverse().find((e) => e.names.includes(name));
  await act(async () => { entry.fn({ data }); });
}

beforeEach(() => {
  _resetDaemonDataCache();
  _resetSessionTranscriptStore();
  h.events = [];
  h.params = { id: 'doc' };
  h.handlers = {
    'host.profile.summaries': () => ({ profiles: [DOC] }),
    'host.sessions.list': () => ({ sessions: [] }),
    'host.workgroups.list': () => ({ workgroups: [WG] }),
    'host.workgroup.transcript': () => ({ posts: [] }),
    'host.workgroup.tasks': () => ({}),
    'host.workgroup.members': () => ({ members: [] }),
  };
});

describe('profile thread with nothing to load', () => {
  it('settles into the empty state when the profile has no sessions', async () => {
    render(<ProfileChat />);
    await settle();
    expect(hasText('start a thread with doc')).toBe(true);
    expect(skeleton()).toBeNull();
  });

  it('never latches the skeleton when the seeded session belongs to another connection', async () => {
    h.handlers['host.profile.summaries'] = () => ({
      profiles: [{ ...DOC, latest_session: { id: 's-desktop', kind: 'chat', updated_at: 10 } }],
    });
    h.handlers['host.session.read'] = () => Promise.reject(notFound());

    render(<ProfileChat />);
    await settle();
    expect(skeleton()).toBeNull();
    expect(hasText('start a thread with doc')).toBe(true);
    expect(document.querySelector('[data-composer]').getAttribute('data-disabled')).toBe('false');
  });

  it('names the subject and the provider-less model in the empty state', async () => {
    render(<ProfileChat />);
    await settle();
    expect(hasText('start a thread with doc')).toBe(true);
    expect(hasText('claude-opus-5')).toBe(true);
    expect(hasText('anthropic/claude-opus-5')).toBe(false);
    expect(document.querySelector('[data-mark]').getAttribute('data-mark')).toBe('#abc123');
  });

  it('keeps the skeleton while a real transcript is still in flight', async () => {
    const read = deferred();
    h.handlers['host.profile.summaries'] = () => ({
      profiles: [{ ...DOC, latest_session: { id: 's1', kind: 'chat', updated_at: 10 } }],
    });
    h.handlers['host.session.read'] = () => read.promise;

    render(<ProfileChat />);
    await settle();
    expect(skeleton()?.getAttribute('data-skeleton')).toBe('profile');
    expect(hasText('start a thread with doc')).toBe(false);
  });

  it('never flashes the empty state while the seeded transcript is on its way', async () => {
    const read = deferred();
    h.handlers['host.profile.summaries'] = () => ({
      profiles: [{ ...DOC, latest_session: { id: 's1', kind: 'chat', updated_at: 10 } }],
    });
    h.handlers['host.session.read'] = () => read.promise;

    const watch = watchFrames();
    render(<ProfileChat />);
    await settle();
    watch.stop();

    expect(watch.sawText('doc')).toBe(true);
    expect(watch.sawText('start a thread with doc')).toBe(false);
    expect(skeleton()).toBeTruthy();
  });

  it('drops the skeleton for the transcript once the read settles', async () => {
    const read = deferred();
    h.handlers['host.profile.summaries'] = () => ({
      profiles: [{ ...DOC, latest_session: { id: 's1', kind: 'chat', updated_at: 10 } }],
    });
    h.handlers['host.session.read'] = () => read.promise;

    render(<ProfileChat />);
    await settle();
    expect(skeleton()).toBeTruthy();

    read.resolve({
      session: { id: 's1', turns: [{ at: 1, user: 'ping', assistant: 'pong' }] },
      total_turns: 1,
      turns_offset: 0,
    });
    await settle();

    expect(skeleton()).toBeNull();
    expect(document.querySelector('[data-list]').getAttribute('data-list')).toBe('1');
    expect(hasText('start a thread with doc')).toBe(false);
  });

  it('shows the empty state for a session that exists with no turns', async () => {
    h.handlers['host.profile.summaries'] = () => ({
      profiles: [{ ...DOC, latest_session: { id: 's1', kind: 'chat', updated_at: 10 } }],
    });
    h.handlers['host.session.read'] = () => ({
      session: { id: 's1', turns: [] },
      total_turns: 0,
      turns_offset: 0,
    });

    render(<ProfileChat />);
    await settle();
    expect(hasText('start a thread with doc')).toBe(true);
    expect(skeleton()).toBeNull();
  });

  it('keeps the empty state through a refresh instead of flashing the skeleton', async () => {
    render(<ProfileChat />);
    await settle();
    expect(hasText('start a thread with doc')).toBe(true);

    h.handlers['host.sessions.list'] = () => deferred().promise;
    await emit('session_changed', { profile: 'doc' });

    expect(skeleton()).toBeNull();
    expect(hasText('start a thread with doc')).toBe(true);
  });
});

describe('workgroup thread with nothing to load', () => {
  beforeEach(() => {
    h.params = { id: 'alpha' };
  });

  it('settles into the same empty hero when the workgroup has no posts', async () => {
    render(<WorkgroupChat />);
    await settle();
    expect(hasText('no posts yet')).toBe(true);
    expect(hasText('direct @scout to open a #task')).toBe(true);
    expect(skeleton()).toBeNull();
  });

  it('keeps the skeleton while the transcript is still in flight, then drops it', async () => {
    const read = deferred();
    h.handlers['host.workgroup.transcript'] = () => read.promise;

    render(<WorkgroupChat />);
    await settle();
    expect(skeleton()?.getAttribute('data-skeleton')).toBe('workgroup');
    expect(hasText('no posts yet')).toBe(false);

    read.resolve({ posts: [{ seq: 1, from: '@scout', from_pubkey: 'k', body: 'hello' }] });
    await settle();

    expect(skeleton()).toBeNull();
    expect(document.querySelector('[data-list]').getAttribute('data-list')).toBe('1');
  });

  it('keeps the empty hero through a refresh instead of flashing the skeleton', async () => {
    render(<WorkgroupChat />);
    await settle();
    expect(hasText('no posts yet')).toBe(true);

    h.handlers['host.workgroup.transcript'] = () => deferred().promise;
    await emit('wg.post', { wg_id: 'alpha' });

    expect(skeleton()).toBeNull();
    expect(hasText('no posts yet')).toBe(true);
  });
});
