import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(async () => {}),
  toast: vi.fn(),
  pathname: '/',
  items: [],
  loading: false,
  role: 'admin',
  endpoint: { id: 'c1', name: 'casa', url: 'ws://casa:49200' },
}));

vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, replace: h.replace }),
  usePathname: () => h.pathname,
  useFocusEffect: (cb) => React.useEffect(() => cb(), [cb]),
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
}));

vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', line: '#eee' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoMedium: 'monoMedium' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
  }),
}));

vi.mock('../src/components/Banner', () => ({ Banner: () => null }));
vi.mock('../src/features/inbox/ConnHeader', () => ({ ConnHeader: () => null }));
vi.mock('../src/features/inbox/InboxRow', () => ({ InboxRow: () => null }));
vi.mock('../src/features/inbox/Roster', () => ({
  Roster: () => React.createElement('div', { 'data-roster': 'true' }),
}));
vi.mock('../src/features/inbox/RowContextSheet', () => ({ RowContextSheet: () => null }));
vi.mock('../src/features/sheets/ConnectionSheet', () => ({ ConnectionSheet: () => null }));
vi.mock('../src/features/sheets/CreateProfileSheet', () => ({ CreateProfileSheet: () => null }));
vi.mock('../src/features/sheets/CreateWorkgroupSheet', () => ({ CreateWorkgroupSheet: () => null }));
vi.mock('../src/features/shell/HomePane', () => ({
  HomePane: () => React.createElement('div', { 'data-home': 'true' }),
}));
vi.mock('../src/features/shell/ShellFooter', () => ({ ShellFooter: () => null }));

vi.mock('../src/components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../src/hooks/useDebouncedCallback', () => ({ useDebouncedCallback: (fn) => fn }));
vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/hooks/useInbox', () => ({
  useInbox: () => ({ items: h.items, loading: h.loading, refresh: h.refresh }),
}));
vi.mock('../src/hooks/useUnifiedOutputs', () => ({ useUnifiedOutputs: () => ({ rows: [] }) }));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({ endpoint: h.endpoint, probeState: new Map([['c1', 'online']]), activeRole: h.role }),
}));
vi.mock('../src/lib/pins', () => ({
  usePins: () => ({
    isProfilePinned: () => false,
    isWorkgroupPinned: () => false,
    toggleProfile: () => {},
    toggleWorkgroup: () => {},
  }),
}));
import { SETTINGS_PATH } from '../src/lib/panes';
import { PaneContext } from '../src/nav/PaneContext';
import { _resetLaunchRestore } from '../src/features/shell/launchRestore';
import { SidebarPane } from '../src/features/shell/SidebarPane';
import Index from '../app/index.jsx';

const DOC = { kind: 'profile', id: 'doc', name: 'doc', label: 'doc', sortKey: 300 };
const AGORA = { kind: 'profile', id: 'agora', name: 'agora', label: 'agora', sortKey: 200 };
const WG = { kind: 'workgroup', id: 'alpha', profile: 'doc', label: 'alpha', sortKey: 400 };
const FRESH = { kind: 'profile', id: 'vera', name: 'vera', label: 'vera', sortKey: 0 };

function mount(twoPane) {
  const node = <Index />;
  if (!twoPane) return render(node);
  return render(
    <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>{node}</PaneContext.Provider>,
  );
}

function remount(rerender, twoPane) {
  const node = <Index />;
  rerender(
    twoPane
      ? <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>{node}</PaneContext.Provider>
      : node,
  );
}

function home() {
  return document.querySelector('[data-home="true"]');
}

beforeEach(() => {
  _resetLaunchRestore();
  h.push.mockClear();
  h.replace.mockClear();
  h.toast.mockClear();
  h.pathname = '/';
  h.items = [];
  h.loading = false;
  h.role = 'admin';
  h.endpoint = { id: 'c1', name: 'casa', url: 'ws://casa:49200' };
});

describe('tablet arrival', () => {
  it('lands on the most recent subject instead of a launcher', () => {
    h.items = [DOC, AGORA];
    mount(true);
    expect(h.replace).toHaveBeenCalledWith('/chat/doc');
    expect(h.push).not.toHaveBeenCalled();
  });

  it('resumes a workgroup when that is the newest thing', () => {
    h.items = [WG, DOC];
    mount(true);
    expect(h.replace).toHaveBeenCalledWith('/wg/alpha');
  });

  it('redirects exactly once, however many rosters land after', () => {
    h.items = [DOC, AGORA];
    const { rerender } = mount(true);
    h.items = [{ ...DOC, sortKey: 900 }, AGORA];
    remount(rerender, true);
    h.items = [AGORA, DOC];
    remount(rerender, true);
    expect(h.replace).toHaveBeenCalledTimes(1);
  });

  it('leaves the subject the user picked afterwards alone', () => {
    h.items = [DOC, AGORA];
    const { rerender } = mount(true);
    h.pathname = '/chat/agora';
    h.items = [{ ...AGORA, sortKey: 999 }, DOC];
    remount(rerender, true);
    expect(h.replace).toHaveBeenCalledTimes(1);
    expect(h.replace).toHaveBeenCalledWith('/chat/doc');
  });

  it('holds on the empty pane when a fresh daemon has nothing to resume', () => {
    h.items = [FRESH];
    mount(true);
    expect(h.replace).not.toHaveBeenCalled();
    expect(h.push).not.toHaveBeenCalled();
    expect(home()).toBeTruthy();
  });

  it('holds on the empty pane while the roster is still loading, then resumes once it lands', () => {
    h.loading = true;
    const { rerender } = mount(true);
    expect(h.replace).not.toHaveBeenCalled();
    expect(home()).toBeTruthy();

    h.loading = false;
    h.items = [DOC];
    remount(rerender, true);
    expect(h.replace).toHaveBeenCalledTimes(1);
    expect(h.replace).toHaveBeenCalledWith('/chat/doc');
  });

  it('never resumes an unpaired device into another daemon roster', () => {
    h.endpoint = null;
    h.items = [DOC, AGORA];
    mount(true);
    expect(h.replace).not.toHaveBeenCalled();
    expect(h.push).not.toHaveBeenCalled();
    expect(home()).toBeTruthy();
  });

  it('stands down when something else already routed the arrival', () => {
    h.pathname = '/chat/agora';
    h.items = [DOC];
    const { rerender } = mount(true);
    h.items = [DOC, AGORA];
    remount(rerender, true);
    expect(h.replace).not.toHaveBeenCalled();
    expect(h.push).not.toHaveBeenCalled();
  });
});

describe('two-pane shell arrival', () => {
  const shell = () => (
    <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>
      <SidebarPane />
      <Index />
    </PaneContext.Provider>
  );

  it('routes the launch once, from the one mechanism that reads history', () => {
    h.items = [FRESH, DOC];
    render(shell());
    expect(h.replace.mock.calls).toEqual([['/chat/doc']]);
    expect(h.push).not.toHaveBeenCalled();
  });

  it('leaves a shell route the launch landed on alone when the roster arrives late', () => {
    h.pathname = SETTINGS_PATH;
    const { rerender } = render(shell());
    h.items = [DOC, AGORA];
    rerender(shell());
    expect(h.replace).not.toHaveBeenCalled();
    expect(h.push).not.toHaveBeenCalled();
  });
});

describe('phone arrival', () => {
  it('stays on the roster and opens no subject, however recent the last chat is', () => {
    h.items = [DOC, AGORA];
    mount(false);
    expect(h.push).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
    expect(document.querySelector('[data-roster]')).toBeTruthy();
  });

  it('keeps standing down as later rosters land', () => {
    h.items = [DOC, AGORA];
    const { rerender } = mount(false);
    h.items = [{ ...DOC, sortKey: 900 }, AGORA];
    remount(rerender, false);
    expect(h.push).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('stays on the roster when a fresh daemon has nothing to resume', () => {
    h.items = [FRESH];
    mount(false);
    expect(h.push).not.toHaveBeenCalled();
    expect(document.querySelector('[data-roster]')).toBeTruthy();
  });
});

describe('resize', () => {
  it('never navigates when the roster is widened into two panes', () => {
    h.items = [DOC, AGORA];
    const { rerender } = mount(false);
    remount(rerender, true);
    expect(h.push).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
    expect(home()).toBeTruthy();
  });

  it('never re-resumes when a tablet is narrowed and widened again', () => {
    h.items = [DOC, AGORA];
    const { rerender } = mount(true);
    expect(h.replace).toHaveBeenCalledTimes(1);
    remount(rerender, false);
    remount(rerender, true);
    expect(h.replace).toHaveBeenCalledTimes(1);
    expect(h.push).not.toHaveBeenCalled();
  });

  it('never navigates when the roster is widened after the user walked off the root', () => {
    h.items = [DOC, AGORA];
    const { rerender } = mount(false);
    h.pathname = '/settings';
    remount(rerender, true);
    expect(h.push).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
  });
});
