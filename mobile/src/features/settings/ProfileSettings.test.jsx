import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';

import { EndpointContext } from '../../lib/EndpointContext';
import { ThemeProvider } from '../../theme/ThemeContext';
import { PaneContext } from '../../nav/PaneContext';
import { _resetDaemonDataCache } from '../../hooks/useDaemonData';

const h = vi.hoisted(() => ({
  params: { id: 'doc' },
  router: { push: vi.fn(), back: vi.fn(), replace: vi.fn() },
  visionSheetProps: null,
  modelSheetProps: null,
  appearanceSheetProps: null,
}));

vi.mock('expo-router', () => ({
  useLocalSearchParams: () => h.params,
  usePathname: () => '/profile/doc/settings',
  useRouter: () => h.router,
  useFocusEffect: (fn) => { fn?.(); },
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children, ...props }) => React.createElement('div', props, children),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...props }) => React.createElement('div', props, children);
  const Text = ({ children, style, ...props }) => React.createElement('span', props, children);
  const Pressable = ({ children, onPress, style, ...props }) => {
    const body = children instanceof Function ? children({ pressed: false }) : children;
    return React.createElement('button', { type: 'button', onClick: onPress, ...props }, body);
  };
  return {
    View,
    Text,
    Pressable,
    ScrollView: ({ children, refreshControl, ...p }) => React.createElement(View, { ...p, 'data-refresh': refreshControl ? 'true' : 'false' }, children),
    RefreshControl: () => null,
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'activity' }),
    StyleSheet: { create: (s) => s, absoluteFillObject: {} },
    useColorScheme: () => 'light',
    useWindowDimensions: () => ({ width: 390, height: 844, scale: 3, fontScale: 1 }),
    Animated: {
      Value: class {
        setValue() {}
        stopAnimation() {}
        interpolate() { return 0; }
      },
      View,
      timing: () => ({ start() {}, stop() {} }),
      sequence: () => ({}),
      loop: () => ({ start() {}, stop() {} }),
    },
  };
});

vi.mock('../../components/ScreenHeader', () => ({
  ScreenHeader: ({ title, subtitle, meta }) => (
    <header>
      <h1>{title}</h1>
      {subtitle ? <span>{subtitle}</span> : null}
      <div data-meta="true">{meta}</div>
    </header>
  ),
}));

vi.mock('../../components/TextPrompt', () => ({ TextPrompt: () => null }));

vi.mock('../../components/Row', () => ({
  SectionHeader: ({ children }) => <h2>{children}</h2>,
  RowGroup: ({ children }) => <div data-row-group="">{children}</div>,
  SettingsBand: ({ children }) => <section>{children}</section>,
  RowSeparator: () => <hr />,
  Row: ({ label, helper, value, spokenValue }) => (
    <div data-spoken={spokenValue}>
      <span>{label}</span>
      {helper ? <small>{helper}</small> : null}
      {value ? <strong>{value}</strong> : null}
    </div>
  ),
}));

vi.mock('../../components/Pill', () => ({
  Pill: ({ children }) => <span>{children}</span>,
}));

vi.mock('../../components/Toggle', () => ({
  Toggle: ({ on, label, onChange, disabled }) => (
    <button type="button" aria-label={label} aria-pressed={!!on} disabled={disabled} onClick={() => { h.lastToggle = onChange?.(!on); }}>
      {on ? 'on' : 'off'}
    </button>
  ),
}));

vi.mock('../../components/SettingsSkeleton', () => ({ SettingsSkeleton: () => <div data-skeleton="true" /> }));

vi.mock('./IdentityEditor', () => ({
  IdentityEditor: ({ profileId }) => <div data-identity-editor={profileId}>Draft</div>,
}));


vi.mock('../../components/TypedConfirm', () => ({
  Bold: ({ children }) => <strong>{children}</strong>,
  Code: ({ children }) => <code>{children}</code>,
  TypedConfirm: ({ open, title, expected }) =>
    open ? <div data-confirm={title} data-expected={String(expected)} /> : null,
}));

vi.mock('../../features/sheets/AppearanceSheet', () => ({
  AppearanceSheet: (props) => {
    h.appearanceSheetProps = props;
    return null;
  },
}));

vi.mock('../../features/sheets/ProfileFieldSheets', () => ({
  BudgetSheet: () => null,
  CleanupSheet: () => null,
  ModelSheet: (props) => {
    if (props.title === 'Vision model') h.visionSheetProps = props;
    if (!props.title) h.modelSheetProps = props;
    return null;
  },
  ReasoningEffortSheet: () => null,
  VoiceSheet: () => null,
  WorkspaceSheet: () => null,
}));

const ProfileSettings = (await import('../../../app/profile/[id]/settings.jsx')).default;

function wrapper(call, twoPane = false, extra = {}) {
  return ({ children }) => (
    <EndpointContext.Provider value={{ endpoint: { id: 'remote' }, call, ...extra }}>
      <ThemeProvider>
        <PaneContext.Provider value={{ twoPane, side: twoPane ? 'detail' : 'full', sidebarOpen: true, toggleSidebar() {} }}>
          {children}
        </PaneContext.Provider>
      </ThemeProvider>
    </EndpointContext.Provider>
  );
}

beforeEach(() => {
  _resetDaemonDataCache();
  h.params = { id: 'doc' };
  h.router = { push: vi.fn(), back: vi.fn(), replace: vi.fn() };
  h.visionSheetProps = null;
  h.modelSheetProps = null;
  h.appearanceSheetProps = null;
});

describe('ProfileSettings snapshot first paint', () => {
  it('renders snapshot sections without firing fallback section RPCs', async () => {
    const calls = [];
    const call = vi.fn(async (method) => {
      calls.push(method);
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'doc', counts: { peers: 2, skills: 4, workgroups: 1 } }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc', model: 'openrouter/example', accent: '#10b981', budget_daily_usd: 2 },
          usage: { days: [{ iso: '2026-06-29', tokIn: 1000, tokOut: 500, cost: 0.12, today: true }] },
          schedules: { jobs: [{ id: 'daily', title: 'Daily brief' }] },
          workgroups: { workgroups: [{ id: 'ops' }] },
          email: { accounts: [{ id: 'inbox', address: 'me@example.com', configured: true }] },
          storage: { storage: [{ key: 'sessions', label: 'sessions', size_bytes: 2048, file_count: 2 }] },
        };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

    render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(screen.getByText(/14-day total \$0\.12/)).toBeTruthy());
    expect(screen.getAllByText('$0.12').length).toBeGreaterThan(0);
    expect(screen.getByText('me@example.com')).toBeTruthy();
    expect(screen.getByText('2 KB')).toBeTruthy();

    expect(calls).not.toContain('host.profile.detail');
    expect(calls).not.toContain('host.email.status');
    expect(calls).not.toContain('host.schedule.list');
    expect(calls).not.toContain('host.profile.storage');
    expect(calls).not.toContain('host.skills.list');
    expect(calls).not.toContain('host.tools.list');
  });

  it('falls back only for sections missing from the snapshot', async () => {
    const calls = [];
    const call = vi.fn(async (method) => {
      calls.push(method);
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'doc', counts: { peers: 0, skills: 0 } }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc' },
          usage: { days: [] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          storage: { storage: [] },
        };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      if (method === 'host.email.status') {
        return { accounts: [{ id: 'fallback', address: 'fallback@example.com', configured: true }] };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

    render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(screen.getByText('fallback@example.com')).toBeTruthy());
    expect(calls).toContain('host.email.status');
    expect(calls).not.toContain('host.schedule.list');
    expect(calls).not.toContain('host.profile.storage');
  });

  it('fetches storage via host.profile.storage when the daemon honors the sections filter', async () => {
    const calls = [];
    const call = vi.fn(async (method, params) => {
      calls.push(method);
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'doc', counts: { peers: 0, skills: 0 } }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        expect(params.sections).toEqual(['detail', 'usage', 'workgroups', 'email', 'schedules']);
        return {
          detail: { name: 'doc' },
          usage: { days: [] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          email: { accounts: [] },
        };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      if (method === 'host.profile.storage') {
        return { storage: [{ key: 'sessions', label: 'sessions', size_bytes: 4096, file_count: 3 }] };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

    render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(screen.getByText('4 KB')).toBeTruthy());
    expect(calls).toContain('host.profile.storage');
  });
});

describe('ProfileSettings routing tiers', () => {
  it('renders tier rows from profile detail, with main-model fallback labels', async () => {
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'doc', counts: {} }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: {
            name: 'doc',
            model: 'openrouter/example',
            tiers: {
              fast: { model: 'openrouter/flash-lite', effort: 'low', reasoning_supported: true },
              deep: { model: '', effort: '', reasoning_supported: false },
            },
          },
          usage: { days: [] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          email: { accounts: [] },
          storage: { storage: [] },
        };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call) });

    const scope = within(container);
    await waitFor(() => expect(scope.getByText('Fast model')).toBeTruthy());
    expect(scope.getByText('flash-lite')).toBeTruthy();
    expect(scope.getByText('Fast reasoning')).toBeTruthy();
    expect(scope.getByText('low')).toBeTruthy();
    expect(scope.getByText('Deep model')).toBeTruthy();
    expect(scope.getByText('main model')).toBeTruthy();
    expect(scope.queryByText('Deep reasoning')).toBeNull();
  });

  it('hides tier rows when the daemon detail has no tiers (old daemon)', async () => {
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'doc', counts: {} }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc', model: 'openrouter/example' },
          usage: { days: [] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          email: { accounts: [] },
          storage: { storage: [] },
        };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call) });

    const scope = within(container);
    await waitFor(() => expect(scope.getByText('Model')).toBeTruthy());
    expect(scope.queryByText('Fast model')).toBeNull();
    expect(scope.queryByText('Deep model')).toBeNull();
    expect(scope.queryByText('Vision model')).toBeNull();
  });
});

describe('ProfileSettings vision model', () => {
  it('renders and saves the read_image override only on supporting daemons', async () => {
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'doc', counts: {} }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: {
            name: 'doc',
            model: 'openrouter/example',
            vision_model: 'openrouter/deepseek/deepseek-v4-flash-vision-exp',
            models: ['openrouter/deepseek/deepseek-v4-flash-vision-exp'],
          },
          usage: { days: [] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          email: { accounts: [] },
          storage: { storage: [] },
        };
      }
      if (method === 'host.config.set_field') return { ok: true };
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call) });
    const scope = within(container);
    await waitFor(() => expect(scope.getByText('Vision model')).toBeTruthy());
    expect(scope.getByText('deepseek-v4-flash-vision-exp')).toBeTruthy();
    await h.visionSheetProps.onSave('openrouter/deepseek/vision-next');
    expect(call).toHaveBeenCalledWith('host.config.set_field', {
      profile: 'doc',
      key: 'tools.read_image.model',
      value: 'openrouter/deepseek/vision-next',
    });
  });
});

describe('ProfileSettings delete intent', () => {
  function daemon() {
    return vi.fn(async (method) => {
      if (method === 'host.profile.summaries') return { profiles: [{ name: 'doc', counts: {} }] };
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc', model: 'openrouter/example' },
          usage: { days: [] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          email: { accounts: [] },
          storage: { storage: [] },
        };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });
  }

  function confirmNode(container) {
    return container.querySelector('[data-confirm]');
  }

  it('opens the delete confirmation once the profile the row menu named has loaded', async () => {
    h.params = { id: 'doc', intent: 'delete' };
    const call = daemon();

    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(confirmNode(container)).toBeTruthy());
    expect(confirmNode(container).getAttribute('data-confirm')).toBe('Delete profile @doc');
    expect(confirmNode(container).getAttribute('data-expected')).toBe('doc');
    expect(call.mock.calls.map(([m]) => m)).not.toContain('host.profile.delete');
  });

  it('stays closed when the screen is opened without the intent', async () => {
    const call = daemon();

    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(within(container).getByText('Delete profile')).toBeTruthy());
    expect(confirmNode(container)).toBeNull();
  });
});

describe('ProfileSettings vocabulary', () => {
  it('calls the entity a profile in the pause helper', async () => {
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'doc', counts: {} }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc', model: 'openrouter/example' },
          usage: { days: [] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          email: { accounts: [] },
          storage: { storage: [] },
        };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call) });

    const scope = within(container);
    await waitFor(() => expect(scope.getByText('Paused')).toBeTruthy());
    expect(scope.getByText("paused profiles can't be chatted and sort last in new-chat")).toBeTruthy();
    expect(container.textContent).not.toMatch(/alpis/i);
  });

  it('opens the model sheet straight away when the chat header asked for it', async () => {
    h.params = { id: 'doc', intent: 'model' };
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'doc', counts: {} }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc', model: 'openrouter/example' },
          usage: { days: [] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          email: { accounts: [] },
          storage: { storage: [] },
        };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

    render(<ProfileSettings />, { wrapper: wrapper(call) });
    await waitFor(() => expect(h.modelSheetProps?.open).toBe(true));
    expect(h.modelSheetProps.initialValue).toBe('openrouter/example');
  });

  it('on two panes puts the model and the budget in the header and both daemon actions on one row', async () => {
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'doc', counts: {} }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc', model: 'openrouter/deepseek/deepseek-v4-flash', budget_daily_usd: 2, budget_used_usd: 0.5 },
          usage: { days: [] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          email: { accounts: [] },
          storage: { storage: [] },
        };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call, true) });
    const scope = within(container);
    await waitFor(() => expect(scope.getByText('Update alpi').closest('button')).toBeTruthy());
    expect(scope.getByText('Restart daemon').closest('button')).toBeTruthy();
    expect(scope.queryByText('Update daemon')).toBeNull();
    const meta = container.querySelector('[data-meta]');
    expect(meta.textContent).toMatch('deepseek-v4-flash');
    expect(meta.textContent).toMatch('$0.50');
    expect(meta.textContent).toMatch('/$2.00');
    expect(container.querySelector('[data-identity-editor="doc"]')).toBeTruthy();
  });

  it('wires pull-to-refresh into the settings scroll view', async () => {
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') return { profiles: [{ name: 'doc', counts: {} }] };
      if (method === 'host.settings.profile_snapshot') {
        return { detail: { name: 'doc' }, usage: { days: [] }, schedules: { jobs: [] }, workgroups: { workgroups: [] }, email: { accounts: [] }, storage: { storage: [] } };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });
    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call) });
    await waitFor(() => expect(container.querySelector('[data-refresh="true"]')).toBeTruthy());
  });

  it('flips a boolean through its switch and never through the row', async () => {
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'doc', counts: {} }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc', model: 'openrouter/example', paused: false, sandbox: false },
          usage: { days: [] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          email: { accounts: [] },
          storage: { storage: [] },
        };
      }
      if (method === 'host.config.set_field') return {};
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call) });
    const scope = within(container);
    await waitFor(() => expect(scope.getByLabelText('Paused')).toBeTruthy());
    scope.getByLabelText('Paused').click();
    await waitFor(() => expect(call).toHaveBeenCalledWith('host.config.set_field', { profile: 'doc', key: 'paused', value: 'true' }));
    expect(scope.getByLabelText('Sandbox network').getAttribute('disabled')).not.toBeNull();
    expect(container.querySelector('[data-identity-editor]')).toBeNull();
  });

  it('hands a failed save back to the switch so it can snap back', async () => {
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') return { profiles: [{ name: 'doc', counts: {} }] };
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc', model: 'openrouter/example', paused: false, sandbox: false },
          usage: { days: [] }, schedules: { jobs: [] }, workgroups: { workgroups: [] }, email: { accounts: [] }, storage: { storage: [] },
        };
      }
      if (method === 'host.config.set_field') throw new Error('daemon said no');
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });
    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call) });
    const scope = within(container);
    await waitFor(() => expect(scope.getByLabelText('Paused')).toBeTruthy());
    scope.getByLabelText('Paused').click();
    await expect(h.lastToggle).rejects.toThrow('daemon said no');
  });

  it('does not report a saved field as failed when only the refresh after it fails', async () => {
    let summariesCalls = 0;
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') {
        summariesCalls += 1;
        if (summariesCalls > 1) throw new Error('offline');
        return { profiles: [{ name: 'doc', counts: {} }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc', model: 'openrouter/example', paused: false, sandbox: false },
          usage: { days: [] }, schedules: { jobs: [] }, workgroups: { workgroups: [] }, email: { accounts: [] }, storage: { storage: [] },
        };
      }
      if (method === 'host.config.set_field') return {};
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });
    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call) });
    const scope = within(container);
    await waitFor(() => expect(scope.getByLabelText('Paused')).toBeTruthy());
    scope.getByLabelText('Paused').click();
    let failure = null;
    try {
      await h.lastToggle;
    } catch (e) {
      failure = e;
    }
    expect(call).toHaveBeenCalledWith('host.config.set_field', { profile: 'doc', key: 'paused', value: 'true' });
    expect(summariesCalls).toBeGreaterThan(1);
    expect(failure).toBeNull();
  });

  it('offers the daemon restart and update as buttons, like desktop', async () => {
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'doc', counts: {} }] };
      }
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc', model: 'openrouter/example' },
          usage: { days: [] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          email: { accounts: [] },
          storage: { storage: [] },
        };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call) });

    const scope = within(container);
    await waitFor(() => expect(scope.getByText('Update alpi')).toBeTruthy());
    expect(scope.getByText('Restart daemon')).toBeTruthy();
    expect(scope.getByText('Restart').closest('button')).toBeTruthy();
    expect(scope.getByText('Update').closest('button')).toBeTruthy();
  });
});

describe('ProfileSettings daemon update on a daemon that cannot update itself', () => {
  const call = vi.fn(async (method) => {
    if (method === 'host.profile.summaries') return { profiles: [{ name: 'doc', counts: {} }] };
    if (method === 'host.settings.profile_snapshot') {
      return {
        detail: { name: 'doc', model: 'openrouter/example' },
        usage: { days: [] },
        schedules: { jobs: [] },
        workgroups: { workgroups: [] },
        email: { accounts: [] },
        storage: { storage: [] },
      };
    }
    if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
    throw new Error(`unexpected ${method}`);
  });
  const docker = {
    installState: new Map([['remote', { installer: 'docker', selfUpdate: false }]]),
    updateState: new Map([['remote', '0.16.19']]),
  };
  const sentence = 'Set the image tag to 0.16.19 in docker-compose.yml, then docker compose up -d.';

  it('shows the manual step in the profile settings row instead of an Update button', async () => {
    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call, false, docker) });
    const scope = within(container);

    await waitFor(() => expect(scope.getByText(sentence)).toBeTruthy());
    expect(scope.getByText('Update alpi')).toBeTruthy();
    expect(scope.queryByText('Update')).toBeNull();
    expect(scope.getByText('Restart').closest('button')).toBeTruthy();
  });

  it('draws no Update row at all while a Docker daemon has nothing newer to install', async () => {
    const { container } = render(<ProfileSettings />, {
      wrapper: wrapper(call, false, { installState: docker.installState, updateState: new Map() }),
    });
    const scope = within(container);

    await waitFor(() => expect(scope.getByText('Restart daemon')).toBeTruthy());
    expect(scope.queryByText('Update alpi')).toBeNull();
    expect(container.textContent).not.toContain('docker-compose.yml');
  });

  it('drops the Update button from the two-pane daemon row and keeps Restart', async () => {
    const { container } = render(<ProfileSettings />, { wrapper: wrapper(call, true, docker) });
    const scope = within(container);

    await waitFor(() => expect(scope.getByText('Restart daemon').closest('button')).toBeTruthy());
    expect(scope.queryByText('Update alpi')).toBeNull();
    expect(container.textContent).toContain(sentence);
  });
});

describe('ProfileSettings appearance', () => {
  beforeEach(cleanup);

  const profileCall = (summary, detail, calls = []) =>
    vi.fn(async (method, params) => {
      calls.push([method, params]);
      if (method === 'host.profile.summaries') return { profiles: [{ name: 'doc', counts: {}, ...summary }] };
      if (method === 'host.settings.profile_snapshot') {
        return { detail: { name: 'doc', ...detail }, usage: { days: [] }, schedules: { jobs: [] }, workgroups: { workgroups: [] }, email: { accounts: [] }, storage: { storage: [] } };
      }
      if (method === 'host.config.set_field') return {};
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });

  it('shows the pair name and the colour on the appearance row', async () => {
    const call = profileCall({ fold: 'shield' }, { accent: '#3899e2' });
    render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(screen.getByText('Appearance')).toBeTruthy());
    expect(screen.getByText('blue shield')).toBeTruthy();
    expect(screen.getByText('#3899e2')).toBeTruthy();
    expect(document.querySelector('svg[data-fold="shield"]')).not.toBeNull();
    expect(screen.queryByText('Accent')).toBeNull();
  });

  it('shows the default profile as the alpaca on a row that cannot be opened', async () => {
    h.params = { id: 'default' };
    const call = profileCall({ name: 'default', fold: 'alpaca' }, { name: 'default', accent: '#f0b447' });
    render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(screen.getByText('Alpaca')).toBeTruthy());
    expect(screen.getByText('brand accent')).toBeTruthy();
    expect(document.querySelector('svg[data-fold="alpaca"]')).not.toBeNull();
    h.params = { id: 'doc' };
  });

  it('names a profile without a fold after the diamond', async () => {
    const call = profileCall({}, { accent: '#f0b447' });
    render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(screen.getByText('amber diamond')).toBeTruthy());
  });

  it('writes the fold and the accent to their own config keys', async () => {
    const calls = [];
    const call = profileCall({ fold: 'shield' }, { accent: '#3899e2' }, calls);
    render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(h.appearanceSheetProps?.initialFold).toBe('shield'));
    expect(h.appearanceSheetProps.initialValue).toBe('#3899e2');

    await h.appearanceSheetProps.onSave({ fold: 'rocket', accent: '#2CB3B5' });
    const writes = calls.filter(([method]) => method === 'host.config.set_field').map(([, params]) => params);
    expect(writes).toEqual([
      { profile: 'doc', key: 'tui.fold', value: 'rocket' },
      { profile: 'doc', key: 'tui.accent', value: '#2cb3b5' },
    ]);

    calls.length = 0;
    await h.appearanceSheetProps.onSave({ accent: '#9b5ad9' });
    expect(calls.filter(([method]) => method === 'host.config.set_field').map(([, params]) => params)).toEqual([
      { profile: 'doc', key: 'tui.accent', value: '#9b5ad9' },
    ]);
  });
});

describe('ProfileSettings phone sections', () => {
  beforeEach(cleanup);
  const groupOf = (text) => screen.getByText(text).closest('[data-row-group]');

  it('puts each section in its own row group, header outside', async () => {
    const call = vi.fn(async (method) => {
      if (method === 'host.profile.summaries') return { profiles: [{ name: 'doc', counts: {} }] };
      if (method === 'host.settings.profile_snapshot') {
        return {
          detail: { name: 'doc', model: 'openrouter/example' },
          usage: { days: [{ iso: '2026-06-29', tokIn: 1000, tokOut: 500, cost: 0.12, today: true }] },
          schedules: { jobs: [] },
          workgroups: { workgroups: [] },
          email: { accounts: [] },
          storage: { storage: [] },
        };
      }
      if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
      throw new Error(`unexpected ${method}`);
    });
    render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(screen.getByText(/14-day total \$0\.12/)).toBeTruthy());
    expect(groupOf('Providers')).not.toBeNull();
    expect(groupOf('Providers')).toBe(groupOf('Workspace'));
    expect(screen.getByText('Overview').closest('[data-row-group]')).toBeNull();
    expect(groupOf(/14-day total/)).not.toBeNull();
    expect(groupOf(/14-day total/)).not.toBe(groupOf('Providers'));
    expect(groupOf('Delete profile')).not.toBe(groupOf('Reclaim space'));
  });
});

describe('ProfileSettings attention', () => {
  beforeEach(cleanup);
  const daemon = (attention) => vi.fn(async (method) => {
    if (method === 'host.profile.summaries') return { profiles: [{ name: 'doc', counts: { skills: 5 } }] };
    if (method === 'host.settings.profile_snapshot') {
      return {
        detail: { name: 'doc' },
        usage: { days: [] },
        schedules: { jobs: [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }] },
        workgroups: { workgroups: [] },
        email: { accounts: [] },
        storage: { storage: [] },
      };
    }
    if (method === 'host.profile.attention') return attention();
    if (method === 'host.profile.attention') return { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
    throw new Error(`unexpected ${method}`);
  });

  const flagged = () => ({
    memory: [{ file: 'MEMORY.md', used: 2400, limit: 2000, pct: 120, over: true }, { file: 'USER.md', used: 3000, limit: 2000, pct: 150, over: true }],
    skills: [{ name: 'review-digest', category: 'research', problem: 'lint', message: 'bad' }],
    schedules: [{ id: 'j1', title: 'Digest', message: 'boom', at: 'x', last_ok_at: null }],
    counts: { memory: 2, skills: 1, schedules: 1 },
    total: 4,
  });

  it('shows a count pill and a helper line on flagged rows only', async () => {
    render(<ProfileSettings />, { wrapper: wrapper(daemon(flagged)) });
    await waitFor(() => expect(screen.getByText('1 fails lint')).toBeTruthy());
    expect(screen.getByText('2 over their limit')).toBeTruthy();
    expect(screen.getByText('1 failed')).toBeTruthy();
    const pill = (label) => document.querySelector(`[accessibilitylabel="${label}"]`)?.textContent;
    expect(pill('1 skill needs you')).toBe('1');
    expect(pill('2 files need you')).toBe('2');
    expect(pill('1 job needs you')).toBe('1');
    expect(screen.getByText('native callable functions')).toBeTruthy();
    expect(screen.getByText('view')).toBeTruthy();
    const spoken = [...document.querySelectorAll('[data-spoken]')].map((n) => n.getAttribute('data-spoken'));
    expect(spoken).toEqual(expect.arrayContaining(['1 skill needs you, 5', '2 files need you, 3 files', '1 job needs you, 4']));
  });

  it('keeps today\'s rows when the daemon does not know the verb', async () => {
    const call = daemon(() => { throw Object.assign(new Error('method-not-found'), { code: -32601 }); });
    render(<ProfileSettings />, { wrapper: wrapper(call) });
    await waitFor(() => expect(screen.getByText('instructions loaded on demand')).toBeTruthy());
    await waitFor(() => expect(call.mock.calls.some(([m]) => m === 'host.profile.attention')).toBe(true));
    expect(screen.getByText('USER · MEMORY · AGENT')).toBeTruthy();
    expect(screen.getByText('disable · fire · delete · add new')).toBeTruthy();
    expect(document.querySelector('[accessibilitylabel*="need"]')).toBeNull();
  });

  it('keeps healthy rows as they are when nothing is flagged', async () => {
    render(<ProfileSettings />, { wrapper: wrapper(daemon(() => ({ memory: [], skills: [], schedules: [], counts: { memory: 0, skills: 0, schedules: 0 }, total: 0 }))) });
    await waitFor(() => expect(screen.getByText('instructions loaded on demand')).toBeTruthy());
    expect(document.querySelector('[accessibilitylabel*="need"]')).toBeNull();
  });
});
