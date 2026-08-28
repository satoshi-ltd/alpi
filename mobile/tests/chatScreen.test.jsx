import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  push: vi.fn(),
  back: vi.fn(),
  call: vi.fn(async () => ({})),
  refreshSummaries: vi.fn(async () => {}),
  refreshSessions: vi.fn(async () => {}),
  refreshSession: vi.fn(async () => {}),
  canAdmin: true,
  status: 'online',
  profile: null,
  ctxTokens: 0,
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement(
      'div',
      { ...p, ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}) },
      children,
    );
  const Text = ({ children, style, numberOfLines, ...p }) => React.createElement('span', p, children);
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
    FlatList: () => null,
    KeyboardAvoidingView: ({ children }) => React.createElement('div', {}, children),
    ScrollView: ({ children, horizontal, directionalLockEnabled, showsHorizontalScrollIndicator, style, contentContainerStyle, ...p }) =>
      React.createElement(
        'div',
        { ...p, 'data-scroll': horizontal ? 'horizontal' : 'vertical' },
        children,
      ),
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('expo-router', () => ({
  usePathname: () => '/chat/doc',
  useRouter: () => ({ push: h.push, back: h.back, canGoBack: () => true }),
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

vi.mock('../src/components/ActionSheet', () => ({
  ActionSheet: ({ open, title, actions = [] }) =>
    open
      ? React.createElement(
          'div',
          { 'data-sheet': title },
          actions.map((a, i) =>
            a.divider
              ? React.createElement('hr', { key: `d-${i}` })
              : React.createElement(
                  'button',
                  { key: a.id, type: 'button', 'data-action': a.id, 'data-detail': a.detail, onClick: a.onPress },
                  a.label,
                )),
        )
      : null,
}));
vi.mock('../src/components/AlpiMark', () => ({ AlpiMark: () => React.createElement('span', { 'data-mark': 'true' }) }));
vi.mock('../src/components/Banner', () => ({
  Banner: ({ kind, children, action }) =>
    React.createElement('div', { 'data-banner': kind, 'data-banner-action': action }, children),
}));
vi.mock('../src/components/Button', () => ({ Button: ({ title }) => React.createElement('button', { type: 'button' }, title) }));
vi.mock('../src/components/Diamond', () => ({ Diamond: () => React.createElement('span', { 'data-diamond': 'true' }) }));
vi.mock('../src/components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../src/components/Meter', () => ({
  Meter: ({ label, value, tail, pct }) =>
    React.createElement('div', { 'data-meter': label, 'data-pct': String(pct) }, `${value}${tail ?? ''}`),
}));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));

vi.mock('../src/features/chat/Bubble', () => ({
  ProfileAssistantMessage: () => null,
  ProfileUserMessage: () => null,
}));
vi.mock('../src/features/chat/ChatSkeleton', () => ({ ChatSkeleton: () => React.createElement('div', { 'data-skeleton': 'chat' }) }));
vi.mock('../src/features/chat/Composer', () => ({
  Composer: ({ disabled, placeholder }) =>
    React.createElement('div', { 'data-composer': placeholder, 'data-disabled': String(!!disabled) }),
}));
vi.mock('../src/features/chat/MessageActionsSheet', () => ({ MessageActionsSheet: () => null }));
vi.mock('../src/features/chat/Reasoning', () => ({ Reasoning: () => null }));
vi.mock('../src/features/chat/SoundWave', () => ({ SoundWave: () => null }));
vi.mock('../src/features/chat/ToolCallRow', () => ({ ToolModule: () => null }));
vi.mock('../src/features/sheets/SessionsSheet', () => ({ SessionsSheet: () => null }));
vi.mock('../src/features/aln/deeplink', () => ({ isForeignConnection: () => false }));

vi.mock('../src/hooks/useActiveRole', () => ({ useCanAdminEarly: () => h.canAdmin }));
vi.mock('../src/hooks/useChatSend', () => ({
  useChatSend: () => ({ send: vi.fn(), isSending: () => false, pendingTurn: null, isStreaming: false }),
}));
vi.mock('../src/hooks/useDaemonData', () => ({
  useProfileSummaries: () => ({
    data: { profiles: h.profile ? [h.profile] : [] },
    loading: false,
    refresh: h.refreshSummaries,
  }),
  useSessionsList: () => ({ data: { sessions: [] }, loading: false, refresh: h.refreshSessions }),
}));
vi.mock('../src/hooks/useDebouncedCallback', () => ({ useDebouncedCallback: (fn) => fn }));
vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/hooks/useSessionTranscript', () => ({
  useSessionTranscript: () => ({
    data: { turns: [], last_ctx_tokens: h.ctxTokens },
    loading: false,
    turnsOffset: 0,
    inFlight: false,
    hasMore: false,
    loadOlder: vi.fn(),
    refresh: h.refreshSession,
  }),
}));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({
    endpoint: { id: 'c1', name: 'casa', url: 'http://casa' },
    activeId: 'c1',
    call: h.call,
    probeState: new Map([['c1', h.status]]),
  }),
}));
vi.mock('../src/lib/readAloud', () => ({ enqueueReadAloud: vi.fn() }));
vi.mock('../src/lib/readState', () => ({ markProfileRead: vi.fn() }));

import { DAEMON_STATUS_BANNERS } from '../src/components/DaemonBanner';
import ProfileChat from '../app/chat/[id].jsx';
import { PaneContext } from '../src/nav/PaneContext';

const READY = {
  name: 'doc',
  accent: '#abc123',
  model: 'anthropic/claude-opus-5',
  provider_keys: ['anthropic'],
  paused: false,
};

function sheet() {
  return document.querySelector('[data-sheet]');
}

function action(id) {
  return document.querySelector(`[data-action="${id}"]`);
}

function openMenu() {
  fireEvent.click(screen.getByLabelText('More'));
}

beforeEach(() => {
  h.push.mockClear();
  h.call.mockClear().mockResolvedValue({});
  h.refreshSummaries.mockClear();
  h.refreshSessions.mockClear();
  h.refreshSession.mockClear();
  h.canAdmin = true;
  h.status = 'online';
  h.ctxTokens = 0;
  h.profile = { ...READY };
});

describe('Profile chat header menu', () => {
  it('opens a sheet instead of navigating to settings', () => {
    render(<ProfileChat />);
    expect(sheet()).toBeNull();
    openMenu();
    expect(sheet()).toBeTruthy();
    expect(h.push).not.toHaveBeenCalled();
  });

  it('carries the eight desktop actions', () => {
    render(<ProfileChat />);
    openMenu();
    expect([...document.querySelectorAll('[data-action]')].map((el) => el.textContent)).toEqual([
      'Profile settings',
      'Pause profile',
      'Auto-read replies',
      'Skills',
      'Memory',
      'Tools',
      'Schedule',
      'Refresh thread',
    ]);
  });

  it('keeps the settings route as the deep destination', () => {
    render(<ProfileChat />);
    openMenu();
    fireEvent.click(action('settings'));
    expect(h.push).toHaveBeenCalledWith('/profile/doc/settings');
  });

  it('routes each brain entry to its own screen', () => {
    render(<ProfileChat />);
    openMenu();
    for (const id of ['skills', 'memory', 'tools', 'schedule']) fireEvent.click(action(id));
    expect(h.push.mock.calls.map(([r]) => r)).toEqual([
      '/profile/doc/brain/skills',
      '/profile/doc/brain/memory',
      '/profile/doc/brain/tools',
      '/profile/doc/schedule',
    ]);
  });

  it('pauses through the same config field the settings screen writes', () => {
    render(<ProfileChat />);
    openMenu();
    fireEvent.click(action('pause'));
    expect(h.call).toHaveBeenCalledWith('host.config.set_field', {
      profile: 'doc',
      key: 'paused',
      value: 'true',
    });
  });

  it('offers Resume once the profile is paused, matching the banner copy', () => {
    h.profile = { ...READY, paused: true };
    render(<ProfileChat />);
    expect(screen.getByText(/resume from ··· to chat/)).toBeTruthy();
    openMenu();
    expect(action('pause').textContent).toBe('Resume profile');
    fireEvent.click(action('pause'));
    expect(h.call).toHaveBeenCalledWith('host.config.set_field', {
      profile: 'doc',
      key: 'paused',
      value: 'false',
    });
  });

  it('toggles auto-read through the voice RPC and shows its state', () => {
    render(<ProfileChat />);
    openMenu();
    expect(action('auto-read').getAttribute('data-detail')).toBe('off');
    fireEvent.click(action('auto-read'));
    expect(h.call).toHaveBeenCalledWith('host.voice.set_auto_read', { profile: 'doc', enabled: true });
  });

  it('refreshes the thread without navigating', () => {
    render(<ProfileChat />);
    openMenu();
    fireEvent.click(action('refresh'));
    expect(h.refreshSession).toHaveBeenCalled();
    expect(h.refreshSessions).toHaveBeenCalled();
    expect(h.push).not.toHaveBeenCalled();
  });

  it('leaves a non-admin the refresh entry only', () => {
    h.canAdmin = false;
    render(<ProfileChat />);
    openMenu();
    expect([...document.querySelectorAll('[data-action]')].map((el) => el.getAttribute('data-action'))).toEqual([
      'refresh',
    ]);
  });
});

describe('Profile chat meters', () => {
  it('draws context and budget as proportional bars', async () => {
    h.ctxTokens = 20_000;
    h.profile = { ...READY, budget_daily_usd: 2, budget_used_usd: 0.5 };
    h.call.mockImplementation(async (method) =>
      method === 'host.model.ctx_window' ? { ctx_window: 200_000 } : {});
    render(<ProfileChat />);

    const budget = document.querySelector('[data-meter="Daily budget"]');
    expect(budget.getAttribute('data-pct')).toBe('0.25');
    expect(budget.textContent).toBe('$0.50/$2.00');

    await waitFor(() => expect(document.querySelector('[data-meter="Context window"]')).toBeTruthy());
    const ctx = document.querySelector('[data-meter="Context window"]');
    expect(ctx.getAttribute('data-pct')).toBe('0.1');
    expect(ctx.textContent).toBe('20K/200K');
  });

  it('omits the context meter until the window is known', () => {
    h.ctxTokens = 20_000;
    render(<ProfileChat />);
    expect(document.querySelector('[data-meter="Context window"]')).toBeNull();
  });

  it('omits the budget meter when no cap is set', () => {
    render(<ProfileChat />);
    expect(document.querySelector('[data-meter="Daily budget"]')).toBeNull();
  });
});

describe('Profile chat model label', () => {
  function shown(text) {
    return [...document.querySelectorAll('span')].filter((el) => el.textContent === text);
  }

  it('names the same provider-less model in the header and the empty state', () => {
    render(<ProfileChat />);
    expect(shown('claude-opus-5').length).toBe(2);
    expect(document.body.textContent).not.toMatch('anthropic/claude-opus-5');
  });

  it('drops the gateway and the vendor from a three-segment id', () => {
    h.profile = { ...READY, model: 'openrouter/deepseek/deepseek-v4-flash-0731' };
    render(<ProfileChat />);
    expect(shown('deepseek-v4-flash-0731').length).toBe(2);
    expect(document.body.textContent).not.toMatch('openrouter');
  });

  it('keeps a bare Ollama id whole', () => {
    h.profile = { ...READY, model: 'llama3', provider_keys: [], provider_ollama: ['llama3'] };
    render(<ProfileChat />);
    expect(shown('llama3').length).toBe(2);
  });
});

describe('Profile chat header layout', () => {
  function metaRow() {
    return document.querySelector('[data-scroll="horizontal"]');
  }

  it('scrolls model and meters while the controls stay outside the row', async () => {
    h.ctxTokens = 20_000;
    h.profile = { ...READY, budget_daily_usd: 2, budget_used_usd: 0.5 };
    h.call.mockImplementation(async (method) =>
      method === 'host.model.ctx_window' ? { ctx_window: 200_000 } : {});
    render(<ProfileChat />);
    await waitFor(() => expect(document.querySelector('[data-meter="Context window"]')).toBeTruthy());

    expect(metaRow().querySelector('[data-meter="Context window"]')).toBeTruthy();
    expect(metaRow().querySelector('[data-meter="Daily budget"]')).toBeTruthy();
    expect(metaRow().textContent).toMatch('claude-opus-5');
    expect(metaRow().querySelector('[aria-label="Sessions"]')).toBeNull();
    expect(metaRow().querySelector('[aria-label="More"]')).toBeNull();
  });

  it('keeps Sessions and the menu hit-testable in both pane modes', () => {
    for (const twoPane of [false, true]) {
      const view = render(
        <PaneContext.Provider value={{ twoPane, side: 'detail' }}>
          <ProfileChat />
        </PaneContext.Provider>,
      );
      expect(document.querySelector('[data-scroll="horizontal"] [aria-label="More"]')).toBeNull();
      expect(screen.getByLabelText('Sessions')).toBeTruthy();
      openMenu();
      expect(sheet()).toBeTruthy();
      view.unmount();
    }
  });
});

describe('Profile chat daemon health', () => {
  it('shows an offline banner in the detail pane and refuses the send', () => {
    h.status = 'offline';
    render(<ProfileChat />);
    expect(document.querySelector('[data-banner="danger"]').textContent).toMatch(/Daemon unreachable/);
    expect(document.querySelector('[data-composer]').getAttribute('data-disabled')).toBe('true');
  });

  it('shows a disabled-connection banner and refuses the send', () => {
    h.status = 'disabled';
    render(<ProfileChat />);
    expect(document.querySelector('[data-banner="warning"]').textContent).toMatch(/disabled by host/);
    expect(document.querySelector('[data-composer]').getAttribute('data-disabled')).toBe('true');
  });

  it('shows an auth-failed banner and refuses the send', () => {
    h.status = 'auth-failed';
    render(<ProfileChat />);
    expect(document.querySelector('[data-banner="danger"]').textContent).toMatch(/Token rejected/);
    expect(document.querySelector('[data-composer]').getAttribute('data-disabled')).toBe('true');
  });

  it('leaves a healthy daemon bannerless with a live composer', () => {
    render(<ProfileChat />);
    expect(document.querySelector('[data-banner]')).toBeNull();
    expect(document.querySelector('[data-composer]').getAttribute('data-disabled')).toBe('false');
  });

  it('explains every down status with the shared mapping copy', () => {
    for (const [status, entry] of Object.entries(DAEMON_STATUS_BANNERS)) {
      h.status = status;
      const view = render(<ProfileChat />);
      const banner = document.querySelector('[data-banner]');
      expect(banner.getAttribute('data-banner'), status).toBe(entry.kind);
      expect(banner.textContent, status).toContain(entry.message);
      expect(document.querySelector('[data-composer]').getAttribute('data-disabled'), status).toBe('true');
      view.unmount();
    }
  });
});
