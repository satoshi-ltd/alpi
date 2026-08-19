import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  push: vi.fn(),
  back: vi.fn(),
  call: vi.fn(async () => ({})),
  refreshWgs: vi.fn(async () => {}),
  refreshTranscript: vi.fn(async () => {}),
  refreshTasks: vi.fn(async () => {}),
  canAdmin: true,
  status: 'online',
  wg: null,
  tasks: null,
  tasksError: null,
  foreign: false,
  endpoint: { id: 'c1', name: 'casa', url: 'http://casa' },
  flat: (style) => {
    const resolved = typeof style === 'function' ? style({ pressed: false }) : style;
    return [resolved].flat(Infinity).filter(Boolean).reduce((acc, s) => ({ ...acc, ...s }), {});
  },
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement(
      'div',
      { ...p, ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}) },
      children,
    );
  const Text = ({ children, style, numberOfLines, ...p }) =>
    React.createElement('span', { ...p, 'data-style': JSON.stringify(h.flat(style)) }, children);
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
  usePathname: () => '/wg/alpha',
  useRouter: () => ({ push: h.push, back: h.back, canGoBack: () => true }),
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
vi.mock('../src/components/Diamond', () => ({ Diamond: () => React.createElement('span', { 'data-diamond': 'true' }) }));
vi.mock('../src/components/Dot', () => ({ Dot: () => React.createElement('span', { 'data-dot': 'true' }) }));
vi.mock('../src/components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../src/components/Meter', () => ({
  Meter: ({ label, value, tail, pct }) =>
    React.createElement('div', { 'data-meter': label, 'data-pct': String(pct) }, `${value}${tail ?? ''}`),
}));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));

vi.mock('../src/features/chat/Bubble', () => ({ WorkgroupMessage: () => null }));
vi.mock('../src/features/chat/ChatSkeleton', () => ({ ChatSkeleton: () => React.createElement('div', { 'data-skeleton': 'wg' }) }));
vi.mock('../src/features/chat/Composer', () => ({
  Composer: ({ disabled, placeholder }) =>
    React.createElement('div', { 'data-composer': placeholder, 'data-disabled': String(!!disabled) }),
}));
vi.mock('../src/features/chat/MarkerCard', () => ({ MarkerCard: () => null }));
vi.mock('../src/features/chat/MessageActionsSheet', () => ({ MessageActionsSheet: () => null }));
vi.mock('../src/features/chat/PipelineStrip', () => ({ PipelineStrip: () => null }));
vi.mock('../src/features/chat/SoundWave', () => ({ SoundWave: () => null }));
vi.mock('../src/features/sheets/TasksSheet', () => ({ TasksSheet: () => null }));
vi.mock('../src/features/aln/deeplink', () => ({ isForeignConnection: () => h.foreign }));

vi.mock('../src/hooks/useActiveRole', () => ({ useCanAdminEarly: () => h.canAdmin }));
vi.mock('../src/hooks/useDaemonData', () => ({
  useProfileSummaries: () => ({ data: { profiles: [] }, loading: false, refresh: vi.fn() }),
  useWorkgroups: () => ({
    data: { workgroups: h.wg ? [h.wg] : [] },
    loading: false,
    refresh: h.refreshWgs,
  }),
  useWorkgroupMembers: () => ({ data: { members: [] }, loading: false, refresh: vi.fn() }),
  useWorkgroupTasks: () => ({ data: h.tasks, loading: false, error: h.tasksError, refresh: h.refreshTasks }),
  useWorkgroupTranscript: () => ({ data: { posts: [] }, loading: false, refresh: h.refreshTranscript }),
}));
vi.mock('../src/hooks/useDebouncedCallback', () => ({ useDebouncedCallback: (fn) => fn }));
vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({
    endpoint: h.endpoint,
    activeId: 'c1',
    call: h.call,
    probeState: new Map([['c1', h.status]]),
  }),
}));
vi.mock('../src/lib/readAloud', () => ({ enqueueReadAloud: vi.fn() }));
vi.mock('../src/lib/readState', () => ({ markWorkgroupRead: vi.fn() }));

import { DAEMON_STATUS_BANNERS } from '../src/components/DaemonBanner';
import WorkgroupChat from '../app/wg/[id].jsx';
import { PaneContext } from '../src/nav/PaneContext';

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

function sheet() {
  return document.querySelector('[data-sheet]');
}

function action(id) {
  return document.querySelector(`[data-action="${id}"]`);
}

function openMenu() {
  fireEvent.click(screen.getByLabelText('More'));
}

function fontOf(text) {
  return JSON.parse(screen.getByText(text).getAttribute('data-style')).fontFamily;
}

beforeEach(() => {
  h.push.mockClear();
  h.call.mockClear().mockResolvedValue({});
  h.refreshWgs.mockClear();
  h.refreshTranscript.mockClear();
  h.refreshTasks.mockClear();
  h.canAdmin = true;
  h.status = 'online';
  h.wg = { ...WG };
  h.tasks = null;
  h.tasksError = null;
  h.foreign = false;
  h.endpoint = { id: 'c1', name: 'casa', url: 'http://casa' };
});

describe('Workgroup header menu', () => {
  it('opens a sheet instead of navigating to settings', () => {
    render(<WorkgroupChat />);
    expect(sheet()).toBeNull();
    openMenu();
    expect(sheet()).toBeTruthy();
    expect(h.push).not.toHaveBeenCalled();
  });

  it('carries the workgroup actions with the workgroup noun', () => {
    render(<WorkgroupChat />);
    openMenu();
    expect([...document.querySelectorAll('[data-action]')].map((el) => el.textContent)).toEqual([
      'Workgroup settings',
      'Pause workgroup',
      'Auto-read replies',
      'Refresh thread',
    ]);
  });

  it('keeps the settings route as the deep destination', () => {
    render(<WorkgroupChat />);
    openMenu();
    fireEvent.click(action('settings'));
    expect(h.push).toHaveBeenCalledWith('/wg/alpha/settings');
  });

  it('offers Resume once paused, matching the banner copy', () => {
    h.wg = { ...WG, paused: true };
    render(<WorkgroupChat />);
    expect(screen.getByText(/Resume from the header\./)).toBeTruthy();
    openMenu();
    expect(action('pause').textContent).toBe('Resume workgroup');
    fireEvent.click(action('pause'));
    expect(h.call).toHaveBeenCalledWith('host.workgroup.action', {
      profile: 'doc',
      wg_id: 'alpha',
      action: 'resume',
    });
  });

  it('pauses through the same action RPC the settings screen uses', () => {
    render(<WorkgroupChat />);
    openMenu();
    fireEvent.click(action('pause'));
    expect(h.call).toHaveBeenCalledWith('host.workgroup.action', {
      profile: 'doc',
      wg_id: 'alpha',
      action: 'pause',
    });
  });

  it('hides pause from a member — only the hub can pause', () => {
    h.wg = { ...WG, is_hub: false };
    render(<WorkgroupChat />);
    openMenu();
    expect(action('pause')).toBeNull();
    expect(action('settings')).toBeTruthy();
  });

  it('toggles auto-read through the workgroup update RPC and shows its state', () => {
    h.wg = { ...WG, auto_read: true };
    render(<WorkgroupChat />);
    openMenu();
    expect(action('auto-read').getAttribute('data-detail')).toBe('on');
    fireEvent.click(action('auto-read'));
    expect(h.call).toHaveBeenCalledWith('host.workgroup.update', {
      profile: 'doc',
      wg_id: 'alpha',
      auto_read: false,
    });
  });

  it('refreshes the thread without navigating', () => {
    render(<WorkgroupChat />);
    openMenu();
    fireEvent.click(action('refresh'));
    expect(h.refreshTranscript).toHaveBeenCalled();
    expect(h.refreshTasks).toHaveBeenCalled();
    expect(h.push).not.toHaveBeenCalled();
  });
});

describe('Workgroup budget meter', () => {
  it('draws a proportional bar when a budget is set', () => {
    h.wg = { ...WG, budget_usd: 4, spent_usd: 3 };
    render(<WorkgroupChat />);
    const meter = document.querySelector('[data-meter="Workgroup budget"]');
    expect(meter.getAttribute('data-pct')).toBe('0.75');
    expect(meter.textContent).toBe('$3.00/$4.00');
  });

  it('stays absent when no budget is set', () => {
    render(<WorkgroupChat />);
    expect(document.querySelector('[data-meter="Workgroup budget"]')).toBeNull();
  });

  it('stays absent on a zero cap', () => {
    h.wg = { ...WG, budget_usd: 0, spent_usd: 0 };
    render(<WorkgroupChat />);
    expect(document.querySelector('[data-meter="Workgroup budget"]')).toBeNull();
  });
});

describe('Workgroup header layout', () => {
  function metaRow() {
    return document.querySelector('[data-scroll="horizontal"]');
  }

  it('scrolls hub, members and budget while the menu stays outside the row', () => {
    h.wg = { ...WG, budget_usd: 4, spent_usd: 3, members: 3 };
    render(<WorkgroupChat />);
    expect(metaRow().textContent).toMatch('@doc · 3 members');
    expect(metaRow().querySelector('[data-meter="Workgroup budget"]')).toBeTruthy();
    expect(metaRow().querySelector('[aria-label="More"]')).toBeNull();
  });

  it('keeps the menu hit-testable in both pane modes', () => {
    for (const twoPane of [false, true]) {
      const view = render(
        <PaneContext.Provider value={{ twoPane, side: 'detail' }}>
          <WorkgroupChat />
        </PaneContext.Provider>,
      );
      expect(document.querySelector('[data-scroll="horizontal"] [aria-label="More"]')).toBeNull();
      openMenu();
      expect(sheet()).toBeTruthy();
      view.unmount();
    }
  });
});

describe('Workgroup daemon health', () => {
  it('shows an offline banner in the detail pane and refuses the send', () => {
    h.status = 'offline';
    render(<WorkgroupChat />);
    expect(document.querySelector('[data-banner="danger"]').textContent).toMatch(/Daemon unreachable/);
    expect(document.querySelector('[data-composer]').getAttribute('data-disabled')).toBe('true');
  });

  it('shows a disabled-connection banner and refuses the send', () => {
    h.status = 'disabled';
    render(<WorkgroupChat />);
    expect(document.querySelector('[data-banner="warning"]').textContent).toMatch(/disabled by host/);
    expect(document.querySelector('[data-composer]').getAttribute('data-disabled')).toBe('true');
  });

  it('shows an auth-failed banner and refuses the send', () => {
    h.status = 'auth-failed';
    render(<WorkgroupChat />);
    expect(document.querySelector('[data-banner="danger"]').textContent).toMatch(/Token rejected/);
    expect(document.querySelector('[data-composer]').getAttribute('data-disabled')).toBe('true');
  });

  it('refuses the send while paused', () => {
    h.wg = { ...WG, paused: true };
    render(<WorkgroupChat />);
    expect(document.querySelector('[data-composer]').getAttribute('data-disabled')).toBe('true');
  });

  it('leaves a healthy daemon bannerless with a live composer', () => {
    render(<WorkgroupChat />);
    expect(document.querySelector('[data-banner]')).toBeNull();
    expect(document.querySelector('[data-composer]').getAttribute('data-disabled')).toBe('false');
  });

  it('explains every down status with the shared mapping copy', () => {
    for (const [status, entry] of Object.entries(DAEMON_STATUS_BANNERS)) {
      h.status = status;
      const view = render(<WorkgroupChat />);
      const banner = document.querySelector('[data-banner]');
      expect(banner.getAttribute('data-banner'), status).toBe(entry.kind);
      expect(banner.textContent, status).toContain(entry.message);
      expect(document.querySelector('[data-composer]').getAttribute('data-disabled'), status).toBe('true');
      view.unmount();
    }
  });
});

describe('Workgroup task-state staleness', () => {
  it('warns that the phase strip and the blocked banner may be out of date', () => {
    h.tasksError = new Error('timeout');
    render(<WorkgroupChat />);
    const banner = document.querySelector('[data-banner="warning"]');
    expect(banner.textContent).toMatch(/Workgroup state unavailable\./);
    expect(banner.textContent).toMatch(/The daemon did not answer, so the phase strip and the blocked banner may be out of date\./);
  });

  it('keeps a stale blocked banner on screen rather than dropping it', () => {
    h.tasksError = new Error('timeout');
    h.tasks = { blocked: { slug: 'qa', reason: 'blocked qa · red gate' }, pipeline_run: null };
    render(<WorkgroupChat />);
    expect(screen.getByText(/Workgroup state unavailable\./)).toBeTruthy();
    expect(screen.getByText(/red gate/)).toBeTruthy();
  });

  it('orders the warning above the blocked and paused banners, as desktop orders them', () => {
    h.tasksError = new Error('timeout');
    h.tasks = { blocked: { slug: 'qa', reason: 'blocked qa · red gate' }, pipeline_run: null };
    h.wg = { ...WG, paused: true };
    render(<WorkgroupChat />);
    const stale = screen.getByText(/Workgroup state unavailable\./);
    const blocked = screen.getByText(/red gate/);
    const paused = screen.getByText(/Resume from the header\./);
    expect(stale.compareDocumentPosition(blocked) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(blocked.compareDocumentPosition(paused) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('stays silent once the task state answers', () => {
    h.tasks = { blocked: null, pipeline_run: null };
    render(<WorkgroupChat />);
    expect(document.querySelector('[data-banner="warning"]')).toBeNull();
    expect(screen.queryByText(/Workgroup state unavailable/)).toBeNull();
  });
});

describe('Workgroup dead-end screens', () => {
  const FOREIGN = /This notification came from a connection that isn't active/;
  const UNPAIRED = 'Pair this phone to a daemon first.';

  function unfamilied(container) {
    return [...container.querySelectorAll('span')]
      .filter((el) => el.textContent.trim())
      .filter((el) => !JSON.parse(el.getAttribute('data-style') ?? '{}').fontFamily)
      .map((el) => el.textContent.trim());
  }

  it('renders the foreign-connection notice in the app sans face, not the system font', () => {
    h.foreign = true;
    render(<WorkgroupChat />);
    expect(fontOf(FOREIGN)).toBe('r');
  });

  it('renders the unpaired notice in the app sans face too', () => {
    h.endpoint = null;
    render(<WorkgroupChat />);
    expect(fontOf(UNPAIRED)).toBe('r');
  });

  it('leaves no copy on either dead end outside the text-size scale', () => {
    h.foreign = true;
    const { container } = render(<WorkgroupChat />);
    expect(unfamilied(container)).toEqual([]);
    cleanup();
    h.foreign = false;
    h.endpoint = null;
    expect(unfamilied(render(<WorkgroupChat />).container)).toEqual([]);
  });
});
