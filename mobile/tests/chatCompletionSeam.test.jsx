import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  call: vi.fn(),
  callStream: vi.fn(),
  handlers: null,
  reads: [],
  refreshSummaries: vi.fn(async () => {}),
  refreshSessions: vi.fn(async () => {}),
  profile: null,
  text: 'hola',
  toast: vi.fn(),
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
        { 'data-list': 'turns' },
        data.map((item, index) =>
          React.createElement(
            'div',
            { key: keyExtractor ? keyExtractor(item, index) : index },
            renderItem({ item, index }),
          )),
      ),
    Dimensions: { get: () => ({ height: 800, width: 400 }) },
    KeyboardAvoidingView: ({ children }) => React.createElement('div', {}, children),
    ScrollView: ({ children, horizontal, directionalLockEnabled, showsHorizontalScrollIndicator, style, contentContainerStyle, ...p }) =>
      React.createElement('div', { ...p, 'data-scroll': horizontal ? 'horizontal' : 'vertical' }, children),
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('expo-router', () => ({
  usePathname: () => '/chat/doc',
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), canGoBack: () => true }),
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
vi.mock('../src/components/AlpiMark', () => ({ AlpiMark: () => React.createElement('span', { 'data-mark': 'true' }) }));
vi.mock('../src/components/Banner', () => ({
  Banner: ({ kind, children }) => React.createElement('div', { 'data-banner': kind }, children),
}));
vi.mock('../src/components/Button', () => ({ Button: ({ title }) => React.createElement('button', { type: 'button' }, title) }));
vi.mock('../src/components/Diamond', () => ({ Diamond: () => React.createElement('span', { 'data-diamond': 'true' }) }));
vi.mock('../src/components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../src/components/Meter', () => ({ Meter: () => null }));
vi.mock('../src/components/Toast', () => ({ useToast: () => h.toast }));

vi.mock('../src/features/chat/Bubble', () => ({
  ProfileAssistantMessage: ({ text }) => React.createElement('span', { 'data-assistant': 'true' }, text),
  ProfileUserMessage: ({ text }) => React.createElement('span', { 'data-user': 'true' }, text),
}));
vi.mock('../src/features/chat/ChatSkeleton', () => ({ ChatSkeleton: () => React.createElement('div', { 'data-skeleton': 'chat' }) }));
vi.mock('../src/features/chat/Composer', () => ({
  Composer: ({ onSend, disabled, busy, onStop }) =>
    React.createElement('div', { 'data-composer': 'true' }, [
      React.createElement(
        'button',
        {
          key: 'send',
          type: 'button',
          'data-send': 'true',
          'data-busy': busy ? 'true' : 'false',
          disabled: !!disabled,
          onClick: () => onSend(h.text, []),
        },
        'send',
      ),
      onStop
        ? React.createElement(
          'button',
          { key: 'stop', type: 'button', 'data-stop': 'true', onClick: () => onStop() },
          'stop',
        )
        : null,
    ]),
}));
vi.mock('../src/features/chat/MessageActionsSheet', () => ({ MessageActionsSheet: () => null }));
vi.mock('../src/features/chat/Reasoning', () => ({ Reasoning: () => null }));
vi.mock('../src/features/chat/SoundWave', () => ({ SoundWave: () => null }));
vi.mock('../src/features/chat/ToolCallRow', () => ({ ToolModule: () => null }));
vi.mock('../src/features/sheets/SessionsSheet', () => ({ SessionsSheet: () => null }));
vi.mock('../src/features/sheets/RunsSheet', () => ({ RunsSheet: () => null }));
vi.mock('../src/features/aln/deeplink', () => ({ isForeignConnection: () => false }));

vi.mock('../src/hooks/useActiveRole', () => ({ useCanAdminEarly: () => true }));
vi.mock('../src/hooks/useDaemonData', () => ({
  useProfileSummaries: () => ({
    data: { profiles: h.profile ? [h.profile] : [] },
    loading: false,
    refresh: h.refreshSummaries,
  }),
  useSessionsList: () => ({ data: { sessions: [] }, loading: false, refresh: h.refreshSessions }),
}));
vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({
    endpoint: { id: 'c1', name: 'casa', url: 'http://casa' },
    activeId: 'c1',
    call: h.call,
    callStream: h.callStream,
    probeState: new Map([['c1', 'online']]),
  }),
}));
vi.mock('../src/lib/readAloud', () => ({ enqueueReadAloud: vi.fn() }));
vi.mock('../src/lib/readState', () => ({ markProfileRead: vi.fn() }));

import ProfileChat from '../app/chat/[id].jsx';
import { _resetSessionTranscriptStore } from '../src/hooks/useSessionTranscript';

const READY = {
  name: 'doc',
  accent: '#abc123',
  model: 'anthropic/claude-opus-5',
  provider_keys: ['anthropic'],
  paused: false,
};

const PREV = { at: 10, ended_at: 11, user: 'previous', assistant: 'earlier reply', tools: [] };
const LANDED = { at: 20, ended_at: 21, user: 'hola', assistant: 'the answer', tools: [] };

function assistantTexts() {
  return [...document.querySelectorAll('[data-assistant]')].map((el) => el.textContent);
}

function userTexts() {
  return [...document.querySelectorAll('[data-user]')].map((el) => el.textContent);
}

function sliceFor(params, all) {
  if (params.after_turn != null) {
    return { session: { id: params.id, turns: all.slice(params.after_turn) }, total_turns: all.length, turns_offset: params.after_turn };
  }
  const offset = Math.max(0, all.length - (params.tail_turns ?? all.length));
  return { session: { id: params.id, turns: all.slice(offset) }, total_turns: all.length, turns_offset: offset };
}

function answerPending(all) {
  const pending = h.reads.splice(0, h.reads.length);
  for (const read of pending) read.resolve(sliceFor(read.params, all));
  return pending.length;
}

async function drainReads(all, rounds = 6) {
  for (let i = 0; i < rounds; i += 1) {
    answerPending(all);
    await Promise.resolve();
    await Promise.resolve();
  }
}

function send() {
  fireEvent.click(document.querySelector('[data-send]'));
}

function stop() {
  fireEvent.click(document.querySelector('[data-stop]'));
}

function readParams() {
  return h.call.mock.calls.filter(([m]) => m === 'host.session.read').map(([, p]) => p);
}

function scriptReads(script) {
  let n = 0;
  h.call.mockImplementation((method, params) => {
    if (method !== 'host.session.read') return Promise.resolve({});
    n += 1;
    const step = script(n);
    return step === null ? Promise.reject(new Error('offline')) : Promise.resolve(sliceFor(params, step));
  });
}

beforeEach(() => {
  _resetSessionTranscriptStore();
  h.reads = [];
  h.handlers = null;
  h.text = 'hola';
  h.profile = { ...READY };
  h.toast.mockClear();
  h.refreshSummaries.mockClear();
  h.refreshSessions.mockClear();
  h.call.mockReset().mockImplementation((method, params) => {
    if (method === 'host.session.read') {
      return new Promise((resolve) => {
        h.reads.push({ params, resolve });
      });
    }
    return Promise.resolve({});
  });
  h.callStream.mockReset().mockImplementation((_method, _params, handlers) => {
    h.handlers = handlers;
    return { cancel: vi.fn(), detach: vi.fn() };
  });
});

describe('a completed turn never leaves the transcript', () => {
  it('survives the stream minting a brand-new session id', async () => {
    render(<ProfileChat />);
    expect(h.reads).toHaveLength(0);

    await act(async () => { send(); });
    act(() => h.handlers.onFrame({ event: 'session_start', session_id: 'sess-9' }));
    act(() => h.handlers.onFrame({ event: 'reply', text: 'the answer', session_id: 'sess-9' }));
    expect(assistantTexts()).toEqual(['the answer']);

    let done;
    await act(async () => { done = h.handlers.onDone(); });
    expect(assistantTexts()).toEqual(['the answer']);
    expect(document.querySelector('[data-skeleton]')).toBeNull();

    await act(async () => {
      await drainReads([LANDED]);
      await done;
    });
    expect(assistantTexts()).toEqual(['the answer']);
    expect(userTexts()).toEqual(['hola']);
    expect(h.call.mock.calls.filter(([m]) => m === 'host.session.read')).toHaveLength(2);
  });

  it('survives a completion refresh that joins a read started before the daemon saved', async () => {
    h.profile = { ...READY, latest_session: { kind: 'chat', id: 'sess-1' } };
    render(<ProfileChat />);
    await waitFor(() => expect(h.reads).toHaveLength(1));

    await act(async () => { send(); });
    act(() => h.handlers.onFrame({ event: 'session_start', session_id: 'sess-1' }));
    act(() => h.handlers.onFrame({ event: 'reply', text: 'the answer', session_id: 'sess-1' }));

    let done;
    await act(async () => { done = h.handlers.onDone(); });

    await act(async () => { answerPending([PREV]); });
    expect(assistantTexts()).toContain('the answer');

    await act(async () => {
      await drainReads([PREV, LANDED]);
      await done;
    });
    expect(assistantTexts()).toEqual(['the answer', 'earlier reply']);
    expect(userTexts()).toEqual(['hola', 'previous']);
  });

  it('recovering a finished turn from the sidecar also waits for the persisted turn', async () => {
    h.call.mockImplementation((method, params) => {
      if (method === 'host.chat.events_since') {
        return Promise.resolve({
          events: [
            { frame: { event: 'session_start', session_id: 'sess-9' } },
            { frame: { event: 'reply', text: 'the answer', session_id: 'sess-9' } },
            { frame: { event: 'done', session_id: 'sess-9' } },
          ],
        });
      }
      if (method === 'host.session.read') {
        return new Promise((resolve) => {
          h.reads.push({ params, resolve });
        });
      }
      return Promise.resolve({});
    });
    render(<ProfileChat />);

    await act(async () => { send(); });
    act(() => h.handlers.onFrame({ event: 'session_start', session_id: 'sess-9' }));

    let errored;
    await act(async () => { errored = h.handlers.onError(new Error('ws died')); });
    expect(assistantTexts()).toEqual(['the answer']);

    await act(async () => {
      await drainReads([LANDED]);
      await errored;
    });
    expect(assistantTexts()).toEqual(['the answer']);
    expect(userTexts()).toEqual(['hola']);
  });
});

describe('a turn is identified by the transcript frontier, not by its text', () => {
  const CONTINUE = { at: 10, ended_at: 10, user: 'continue', assistant: 'first answer', tools: [] };
  const MENTION = { at: 20, ended_at: 21, user: '@alice hey can you check?', assistant: 'she says yes', tools: [] };

  it('never swallows a repeated question: the streamed answer holds its place until the read carries it', async () => {
    const AGAIN = { at: 20, ended_at: 21, user: 'continue', assistant: 'second answer', tools: [] };
    h.text = 'continue';
    h.profile = { ...READY, latest_session: { kind: 'chat', id: 'sess-1' } };
    render(<ProfileChat />);
    await act(async () => { await drainReads([CONTINUE]); });
    expect(assistantTexts()).toEqual(['first answer']);

    await act(async () => { send(); });
    act(() => h.handlers.onFrame({ event: 'session_start', session_id: 'sess-1' }));
    act(() => h.handlers.onFrame({ event: 'reply', text: 'second answer' }));
    let done;
    await act(async () => { done = h.handlers.onDone(); });
    expect(assistantTexts()).toEqual(['second answer', 'first answer']);

    await act(async () => {
      await drainReads([CONTINUE, AGAIN]);
      await done;
    });
    expect(assistantTexts()).toEqual(['second answer', 'first answer']);
    expect(userTexts()).toEqual(['continue', 'continue']);
  });

  it('shows exactly one copy of an @-mention turn, which the daemon persists under a rewritten user string', async () => {
    h.text = 'hey @alice can you check?';
    render(<ProfileChat />);

    await act(async () => { send(); });
    act(() => h.handlers.onFrame({ event: 'session_start', session_id: 'sess-9' }));
    act(() => h.handlers.onFrame({ event: 'reply', text: 'she says yes' }));
    let done;
    await act(async () => { done = h.handlers.onDone(); });
    await act(async () => {
      await drainReads([MENTION]);
      await done;
    });

    expect(userTexts()).toEqual(['@alice hey can you check?']);
    expect(assistantTexts()).toEqual(['she says yes']);
  });

  it('refuses a second send while the turn is still streaming', async () => {
    render(<ProfileChat />);
    await act(async () => { send(); });
    expect(document.querySelector('[data-send]').getAttribute('data-busy')).toBe('true');
    expect(document.querySelector('[data-stop]')).not.toBeNull();

    h.text = 'otra';
    await act(async () => { send(); });
    expect(h.callStream).toHaveBeenCalledTimes(1);
    expect(userTexts()).toEqual(['hola']);
  });

  it('refuses a double tap that lands in one batch, before any re-render', async () => {
    render(<ProfileChat />);
    await act(async () => {
      send();
      send();
    });
    expect(h.callStream).toHaveBeenCalledTimes(1);
    expect(userTexts()).toEqual(['hola']);
    expect(h.callStream.mock.calls[0][1].text).toBe('hola');
  });

  it('stopping a turn keeps the partial on screen while the read it triggers is still in flight', async () => {
    render(<ProfileChat />);

    await act(async () => { send(); });
    act(() => h.handlers.onFrame({ event: 'session_start', session_id: 'sess-9' }));
    act(() => h.handlers.onFrame({ event: 'reply', text: 'partial answer' }));

    await act(async () => { stop(); });
    expect(assistantTexts()).toEqual(['partial answer']);
    expect(userTexts()).toEqual(['hola']);

    const INTERRUPTED = { at: 20, ended_at: 21, user: 'hola', assistant: 'partial answer', tools: [], unfinished: true };
    await act(async () => { await drainReads([INTERRUPTED]); });
    expect(assistantTexts()).toEqual(['partial answer']);
    expect(userTexts()).toEqual(['hola']);
  });

  it('stopping a turn pulls the interrupted turn the daemon kept', async () => {
    const INTERRUPTED = { at: 20, ended_at: 21, user: 'hola', assistant: 'partial', tools: [], unfinished: true };
    scriptReads(() => [INTERRUPTED]);
    render(<ProfileChat />);

    await act(async () => { send(); });
    act(() => h.handlers.onFrame({ event: 'session_start', session_id: 'sess-9' }));
    act(() => h.handlers.onFrame({ event: 'assistant_delta', text: 'part' }));
    const before = readParams().length;

    await act(async () => { stop(); });
    expect(readParams().length).toBeGreaterThan(before);
    await waitFor(() => expect(assistantTexts()).toEqual(['partial']));
    expect(userTexts()).toEqual(['hola']);
  });
});

describe('a read that never carries the turn is surfaced, not silent', () => {
  it('tells the reader the transcript did not load instead of blanking the turn quietly', async () => {
    scriptReads(() => null);
    render(<ProfileChat />);

    await act(async () => { send(); });
    act(() => h.handlers.onFrame({ event: 'session_start', session_id: 'sess-9' }));
    act(() => h.handlers.onFrame({ event: 'assistant_delta', text: 'the answer' }));
    await act(async () => { h.handlers.onDone({ session_id: 'sess-9' }); });

    await waitFor(() => expect(h.toast).toHaveBeenCalled());
    expect(h.toast.mock.calls[0][0].title).toMatch(/not shown/i);
  });

  it('does not hold the turn on screen waiting for the sessions list, so nothing renders twice', async () => {
    h.refreshSessions.mockImplementation(() => new Promise(() => {}));
    scriptReads(() => [LANDED]);
    render(<ProfileChat />);

    await act(async () => { send(); });
    act(() => h.handlers.onFrame({ event: 'session_start', session_id: 'sess-9' }));
    act(() => h.handlers.onFrame({ event: 'assistant_delta', text: 'the answer' }));
    await act(async () => { h.handlers.onDone({ session_id: 'sess-9' }); });

    await waitFor(() => expect(assistantTexts()).toEqual(['the answer']));
    expect(userTexts()).toEqual(['hola']);
  });

  it('survives two stop taps landing in one batch', async () => {
    const INTERRUPTED = { at: 20, ended_at: 21, user: 'hola', assistant: 'partial', tools: [], unfinished: true };
    scriptReads(() => [INTERRUPTED]);
    render(<ProfileChat />);

    await act(async () => { send(); });
    act(() => h.handlers.onFrame({ event: 'session_start', session_id: 'sess-9' }));
    act(() => h.handlers.onFrame({ event: 'reply', text: 'partial' }));

    await act(async () => { stop(); stop(); });
    expect(userTexts()).toEqual(['hola']);
    expect(assistantTexts()).toEqual(['partial']);
  });
});
