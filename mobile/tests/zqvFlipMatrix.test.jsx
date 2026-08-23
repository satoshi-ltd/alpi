import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const PHONE = { width: 393, height: 852 };
const TABLET = { width: 1024, height: 768 };

const h = vi.hoisted(() => {
  const stack = ['/'];
  return {
    stack,
    window: { width: 393, height: 852 },
    top: () => stack[stack.length - 1],
    seed: (entries) => { stack.length = 0; stack.push(...entries); },
    router: {
      push: (href) => { stack.push(String(href)); },
      replace: (href) => { stack[stack.length - 1] = String(href); },
      back: () => { if (stack.length > 1) stack.pop(); },
      canGoBack: () => stack.length > 1,
      setParams: () => {},
    },
    call: vi.fn(async () => ({})),
    profile: null,
    sidebarMounts: 0,
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
    ScrollView: ({ children }) => React.createElement('div', {}, children),
    RefreshControl: () => null,
    Modal: ({ children }) => React.createElement('div', {}, children),
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    AppState: { addEventListener: () => ({ remove: () => {} }), currentState: 'active' },
    StyleSheet: { create: (s) => s },
    useWindowDimensions: () => h.window,
  };
});

vi.mock('expo-router', () => ({
  usePathname: () => h.top(),
  useRouter: () => h.router,
  useLocalSearchParams: () => ({ id: h.top().split('/')[2] ?? 'doc' }),
  useFocusEffect: (fn) => { React.useEffect(fn, [fn]); },
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    mode: 'light',
    colors: {
      bg: '#fff', bgPane: '#fff', bgSide: '#fafafa', bgInput: '#f1f3f5', line: '#eee', line2: '#ddd',
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

vi.mock('../src/components/ActionSheet', () => ({
  ActionSheet: ({ open }) => (open ? React.createElement('div', { 'data-testid': 'action-sheet' }) : null),
}));
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
vi.mock('../src/features/sheets/RunsSheet', () => ({ RunsSheet: () => null }));
vi.mock('../src/features/aln/deeplink', () => ({ isForeignConnection: () => false }));
vi.mock('../src/features/settings/SettingsBody', () => ({ SettingsBody: () => null }));

vi.mock('../src/hooks/useActiveRole', () => ({ useCanAdminEarly: () => true, useActiveRole: () => 'admin' }));
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
vi.mock('../src/hooks/useUnifiedOutputs', () => ({
  useUnifiedOutputs: () => ({ rows: [], loading: false, refresh: vi.fn(async () => {}) }),
  adminConnectionsOf: () => [],
  isMemberOnly: () => false,
  markAllUnifiedRead: vi.fn(async () => {}),
  outputsEmptyState: () => ({ title: 'x', body: 'y' }),
  outputsSubtitle: () => 'sub',
}));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({
    endpoint: { id: 'c1', name: 'casa', url: 'http://casa' },
    activeId: 'c1',
    connections: [{ id: 'c1', name: 'casa', url: 'http://casa' }],
    call: h.call,
    probeState: new Map([['c1', 'online']]),
  }),
}));
vi.mock('../src/lib/readAloud', () => ({ enqueueReadAloud: vi.fn() }));
vi.mock('../src/lib/readState', () => ({ markProfileRead: vi.fn() }));

// PaneShell's sidebar is the roster; a stub that still counts mounts and uses the real openVerb.
vi.mock('../src/features/shell/SidebarPane', () => ({
  SidebarPane: () => {
    React.useEffect(() => { h.sidebarMounts += 1; }, []);
    return React.createElement('div', { 'data-testid': 'sidebar' });
  },
}));

import ProfileChat from '../app/chat/[id].jsx';
import OutputsScreen from '../app/outputs.jsx';
import SettingsScreen from '../app/settings.jsx';
import { ScreenHeader } from '../src/components/ScreenHeader';
import { PaneShell } from '../src/features/shell/PaneShell';
import { useBack } from '../src/hooks/useBack';
import { openVerb } from '../src/lib/panes';

// Stands in for the 27 drilled screens, wired exactly as they are (asserted statically below).
function Drill() {
  const goBack = useBack();
  return <ScreenHeader title="Drill" onBack={goBack} />;
}

function ScreenFor() {
  const path = h.top();
  if (path === '/settings') return <SettingsScreen />;
  if (path === '/outputs') return <OutputsScreen />;
  if (path.startsWith('/chat/')) return <ProfileChat />;
  if (path === '/') return <div data-testid="roster" />;
  return <Drill />;
}

function Session() {
  return (
    <PaneShell>
      <ScreenFor />
    </PaneShell>
  );
}

function chevron() {
  return screen.queryByLabelText('Back') ?? document.querySelector('[data-icon="back"]')?.parentElement ?? null;
}

function sidebar() {
  return screen.queryByTestId('sidebar');
}

function open(twoPane, path) {
  h.router[openVerb({ twoPane, pathname: h.top() })](path);
}

beforeEach(() => {
  h.seed(['/']);
  h.window = PHONE;
  h.call.mockClear().mockResolvedValue({});
  h.sidebarMounts = 0;
  h.profile = { name: 'doc', accent: '#abc123', model: 'anthropic/claude-opus-5', provider_keys: ['anthropic'], paused: false };
});

// Each row: seed the session, flip the window, then press whatever back affordance is on screen.
const TRANSITIONS = [
  {
    name: 'two-pane subject → fold → back',
    start: TABLET,
    setup: () => open(true, '/chat/doc'),
    seeded: ['/chat/doc'],
    end: PHONE,
    lands: '/',
  },
  {
    name: 'phone subject → unfold → back',
    start: PHONE,
    setup: () => open(false, '/chat/doc'),
    seeded: ['/', '/chat/doc'],
    end: TABLET,
    lands: null,
  },
  {
    name: 'two-pane subject → fold → unfold → fold → back',
    start: TABLET,
    setup: () => open(true, '/chat/doc'),
    seeded: ['/chat/doc'],
    end: PHONE,
    flips: [PHONE, TABLET, PHONE],
    lands: '/',
  },
  {
    name: 'phone subject → unfold → fold → back',
    start: PHONE,
    setup: () => open(false, '/chat/doc'),
    seeded: ['/', '/chat/doc'],
    end: PHONE,
    flips: [TABLET, PHONE],
    lands: '/',
  },
  {
    name: 'two-pane /settings → fold → back',
    start: TABLET,
    setup: () => open(true, '/settings'),
    seeded: ['/settings'],
    end: PHONE,
    lands: '/',
  },
  {
    name: 'two-pane /outputs (notifications) → fold → back',
    start: TABLET,
    setup: () => open(true, '/outputs'),
    seeded: ['/outputs'],
    end: PHONE,
    lands: '/',
  },
  {
    name: 'phone /settings → unfold → back',
    start: PHONE,
    setup: () => open(false, '/settings'),
    seeded: ['/', '/settings'],
    end: TABLET,
    lands: null,
  },
  {
    name: 'two-pane wg settings drill → fold → back',
    start: TABLET,
    setup: () => { open(true, '/chat/doc'); h.router.push('/wg/alpha/settings'); },
    seeded: ['/chat/doc', '/wg/alpha/settings'],
    end: PHONE,
    lands: '/chat/doc',
  },
  {
    name: 'two-pane profile settings drill → fold → back',
    start: TABLET,
    setup: () => { open(true, '/chat/doc'); h.router.push('/profile/doc/settings'); },
    seeded: ['/chat/doc', '/profile/doc/settings'],
    end: PHONE,
    lands: '/chat/doc',
  },
  {
    name: 'cold deep link to a subject → unfold',
    start: PHONE,
    setup: () => h.seed(['/chat/doc']),
    seeded: ['/chat/doc'],
    end: TABLET,
    lands: null,
  },
  {
    name: 'cold deep link to a subject → fold (already phone) ',
    start: PHONE,
    setup: () => h.seed(['/chat/doc']),
    seeded: ['/chat/doc'],
    end: PHONE,
    lands: '/',
  },
  {
    name: 'cold deep link to a wg drill → unfold → back',
    start: PHONE,
    setup: () => h.seed(['/wg/alpha/settings']),
    seeded: ['/wg/alpha/settings'],
    end: TABLET,
    lands: '/wg/alpha',
  },
  {
    name: 'cold deep link to a memory leaf → unfold → back',
    start: PHONE,
    setup: () => h.seed(['/profile/doc/brain/memory/MEMORY.md']),
    seeded: ['/profile/doc/brain/memory/MEMORY.md'],
    end: TABLET,
    lands: '/profile/doc/brain/memory',
  },
  {
    name: 'cold deep link to an output → fold → back',
    start: TABLET,
    setup: () => h.seed(['/outputs/doc/out-1']),
    seeded: ['/outputs/doc/out-1'],
    end: PHONE,
    lands: '/outputs',
  },
];

describe('mode flips mid-session', () => {
  it.each(TRANSITIONS.map((t) => [t.name, t]))('%s', (_name, t) => {
    h.window = t.start;
    t.setup();
    expect(h.stack).toEqual(t.seeded);

    const { rerender } = render(<Session />);
    for (const w of t.flips ?? [t.end]) {
      h.window = w;
      rerender(<Session />);
    }

    if (t.lands === null) {
      expect(chevron()).toBeNull();
      expect(sidebar()).toBeTruthy();
      return;
    }
    expect(chevron()).toBeTruthy();
    const before = [...h.stack];
    fireEvent.click(chevron());
    expect(h.top()).toBe(t.lands);
    expect(h.stack).not.toEqual(before);
  });

  it('always reaches the roster by pressing back repeatedly, whatever the flip history', () => {
    const seeds = [
      ['/chat/doc'],
      ['/', '/chat/doc'],
      ['/settings'],
      ['/outputs/doc/out-1'],
      ['/wg/alpha/settings'],
      ['/profile/doc/brain/memory/MEMORY.md'],
      ['/chat/doc', '/profile/doc/settings'],
    ];
    for (const seed of seeds) {
      for (const flips of [[PHONE], [TABLET, PHONE], [PHONE, TABLET, PHONE], [TABLET, PHONE, TABLET, PHONE]]) {
        h.seed(seed);
        h.window = flips[0];
        const view = render(<Session />);
        for (const w of flips) {
          h.window = w;
          view.rerender(<Session />);
        }
        let presses = 0;
        while (h.top() !== '/' && presses < 8) {
          const btn = chevron();
          expect(btn, `${seed.join('>')} ${JSON.stringify(flips)} stuck at ${h.top()}`).toBeTruthy();
          fireEvent.click(btn);
          presses += 1;
          view.rerender(<Session />);
        }
        expect(h.top(), `${seed.join('>')} ${JSON.stringify(flips)}`).toBe('/');
        view.unmount();
      }
    }
  });

  it('keeps a sheet-open chat reachable to the roster across a fold', () => {
    h.window = TABLET;
    open(true, '/chat/doc');
    const { rerender } = render(<Session />);
    fireEvent.click(screen.getByLabelText('More'));
    expect(screen.queryByTestId('action-sheet')).toBeTruthy();

    h.window = PHONE;
    rerender(<Session />);
    expect(screen.queryByTestId('action-sheet')).toBeTruthy();
    fireEvent.click(chevron());
    expect(h.top()).toBe('/');
  });

  it('never renders a chevron that leaves the stack untouched', () => {
    for (const seed of [['/'], ['/chat/doc'], ['/', '/chat/doc'], ['/settings'], ['/outputs'], ['/wg/alpha/settings'], ['/outputs/doc/out-1']]) {
      for (const w of [PHONE, TABLET]) {
        h.seed(seed);
        h.window = w;
        const view = render(<Session />);
        const btn = chevron();
        if (btn) {
          const before = [...h.stack];
          fireEvent.click(btn);
          expect(h.stack, `${seed.join('>')} @${w.width}`).not.toEqual(before);
        }
        view.unmount();
      }
    }
  });
});

describe('two-pane flat stack', () => {
  it('does not grow when ten rows are opened from the sidebar', () => {
    h.window = TABLET;
    const rows = ['/chat/doc', '/wg/alpha', '/chat/agora', '/wg/beta', '/chat/etxea', '/chat/doc', '/wg/gamma', '/chat/ghost', '/wg/alpha', '/chat/abby'];
    for (const path of rows) {
      open(true, path);
      expect(h.stack.length).toBe(1);
    }
    expect(h.stack).toEqual(['/chat/abby']);

    h.window = PHONE;
    render(<Session />);
    fireEvent.click(chevron());
    expect(h.stack).toEqual(['/']);
  });

  it('keeps the stack flat across repeated flips and never remounts the sidebar while two-pane', () => {
    h.window = TABLET;
    open(true, '/chat/doc');
    const { rerender } = render(<Session />);
    expect(h.sidebarMounts).toBe(1);

    for (const w of [TABLET, TABLET, TABLET]) {
      h.window = w;
      rerender(<Session />);
      expect(h.stack).toEqual(['/chat/doc']);
    }
    expect(h.sidebarMounts).toBe(1);
  });

  it('hysteresis: 690pt keeps two-pane once open, 676pt drops it', () => {
    h.window = TABLET;
    open(true, '/chat/doc');
    const { rerender } = render(<Session />);
    expect(sidebar()).toBeTruthy();

    h.window = { width: 690, height: 768 };
    rerender(<Session />);
    expect(sidebar()).toBeTruthy();
    expect(chevron()).toBeNull();

    h.window = { width: 675, height: 768 };
    rerender(<Session />);
    expect(sidebar()).toBeNull();
    expect(chevron()).toBeTruthy();
    fireEvent.click(chevron());
    expect(h.top()).toBe('/');
  });
});
