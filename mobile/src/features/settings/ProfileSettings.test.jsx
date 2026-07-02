import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

import { EndpointContext } from '../../lib/EndpointContext';
import { ThemeProvider } from '../../theme/ThemeContext';
import { _resetDaemonDataCache } from '../../hooks/useDaemonData';

const h = vi.hoisted(() => ({
  params: { id: 'doc' },
  router: { push: vi.fn(), back: vi.fn(), replace: vi.fn() },
}));

vi.mock('expo-router', () => ({
  useLocalSearchParams: () => h.params,
  useRouter: () => h.router,
  useFocusEffect: (fn) => { fn?.(); },
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children, ...props }) => React.createElement('div', props, children),
}));

vi.mock('react-native', () => {
  const View = ({ children, ...props }) => React.createElement('div', props, children);
  const Text = ({ children, ...props }) => React.createElement('span', props, children);
  const Pressable = ({ children, onPress, ...props }) => {
    const body = children instanceof Function ? children({ pressed: false }) : children;
    return React.createElement('button', { type: 'button', onClick: onPress, ...props }, body);
  };
  return {
    View,
    Text,
    Pressable,
    ScrollView: View,
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'activity' }),
    useColorScheme: () => 'light',
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
  ScreenHeader: ({ title, subtitle }) => (
    <header>
      <h1>{title}</h1>
      {subtitle ? <span>{subtitle}</span> : null}
    </header>
  ),
}));

vi.mock('../../components/Row', () => ({
  SectionHeader: ({ children }) => <h2>{children}</h2>,
  RowSeparator: () => <hr />,
  Row: ({ label, helper, value }) => (
    <div>
      <span>{label}</span>
      {helper ? <small>{helper}</small> : null}
      {value ? <strong>{value}</strong> : null}
    </div>
  ),
}));

vi.mock('../../components/Pill', () => ({
  Pill: ({ children }) => <span>{children}</span>,
}));

vi.mock('../../components/OnOff', () => ({
  OnOff: ({ on }) => <span>{on ? 'on' : 'off'}</span>,
}));

vi.mock('../../components/Diamond', () => ({
  Diamond: () => <span />,
}));

vi.mock('../../components/TypedConfirm', () => ({
  Bold: ({ children }) => <strong>{children}</strong>,
  Code: ({ children }) => <code>{children}</code>,
  TypedConfirm: () => null,
}));

vi.mock('../../features/sheets/AccentSheet', () => ({
  AccentSheet: () => null,
}));

vi.mock('../../features/sheets/ProfileFieldSheets', () => ({
  BudgetSheet: () => null,
  ModelSheet: () => null,
  ReasoningEffortSheet: () => null,
  VoiceSheet: () => null,
  WorkspaceSheet: () => null,
}));

const ProfileSettings = (await import('../../../app/profile/[id]/settings.jsx')).default;

function wrapper(call) {
  return ({ children }) => (
    <EndpointContext.Provider value={{ endpoint: { id: 'remote' }, call }}>
      <ThemeProvider>{children}</ThemeProvider>
    </EndpointContext.Provider>
  );
}

beforeEach(() => {
  _resetDaemonDataCache();
  h.params = { id: 'doc' };
  h.router = { push: vi.fn(), back: vi.fn(), replace: vi.fn() };
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
      throw new Error(`unexpected ${method}`);
    });

    render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(screen.getByText('14-day total')).toBeTruthy());
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
      if (method === 'host.email.status') {
        return { accounts: [{ id: 'fallback', address: 'fallback@example.com', configured: true }] };
      }
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
      if (method === 'host.profile.storage') {
        return { storage: [{ key: 'sessions', label: 'sessions', size_bytes: 4096, file_count: 3 }] };
      }
      throw new Error(`unexpected ${method}`);
    });

    render(<ProfileSettings />, { wrapper: wrapper(call) });

    await waitFor(() => expect(screen.getByText('4 KB')).toBeTruthy());
    expect(calls).toContain('host.profile.storage');
  });
});
