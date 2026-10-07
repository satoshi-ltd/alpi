import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  params: { id: 'abby', job: 'j-mail' },
  push: vi.fn(),
  call: vi.fn(async () => ({})),
  alert: vi.fn(),
  att: null,
  jobs: [
    { id: 'j-first', kind: 'cron', expression: '0 6 * * 1', prompt: 'first prompt', title: 'First' },
    {
      id: 'j-mail', kind: 'cron', expression: '30 7 * * *', prompt: 'mail prompt', title: 'Mail',
      last_run_at: '2026-10-03T07:30:00Z', last_run_status: 'error', run_timeout: null,
      timeout_error: "'timeout' must be a whole number of seconds",
    },
  ],
}));

vi.mock('react-native', () => {
  const View = ({ children, accessibilityLabel }) => React.createElement('div', accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-color': style?.color }, children);
  const Pressable = ({ children, onPress, accessibilityLabel, style }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-minheight': (typeof style === 'function' ? style({ pressed: false }) : style)?.minHeight }, typeof children === 'function' ? children({ pressed: false }) : children);
  return {
    View, Text, Pressable,
    ScrollView: ({ children }) => React.createElement('div', {}, children),
    RefreshControl: () => null,
    ActivityIndicator: () => null,
    Alert: { alert: (...a) => h.alert(...a) },
  };
});
vi.mock('expo-router', () => ({ useLocalSearchParams: () => h.params, useRouter: () => ({ push: h.push }) }));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', danger: '#f00', dangerText: '#a00', hover: '#eee', selected: '#ddd', line: '#eee', bg: '#fff' },
    fonts: { sans: { regular: 'r', semibold: 's' }, mono: 'm' },
    fontSizes: { xs: 11, sm: 12, md: 13, lg: 15, xl: 18 },
  }),
}));
vi.mock('../src/components/ActionSheet', () => ({
  ActionSheet: ({ open, actions }) => (open
    ? React.createElement('div', { 'data-sheet': 'more' }, actions.map((a) => React.createElement('button', { key: a.id, type: 'button', onClick: a.onPress }, a.label)))
    : null),
}));
vi.mock('../src/components/Button', () => ({ Button: ({ title, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, title) }));
vi.mock('../src/components/Icon', () => ({ Icon: () => null }));
vi.mock('../src/components/RichText', () => ({ RichText: ({ children }) => React.createElement('p', {}, children) }));
vi.mock('../src/components/Row', () => ({
  Row: ({ label }) => React.createElement('div', {}, label),
  RowGroup: ({ children }) => React.createElement('div', {}, children),
  RowSeparator: () => null,
  SectionHeader: ({ children }) => React.createElement('h2', {}, children),
}));
vi.mock('../src/components/Dot', () => ({ Dot: ({ color }) => React.createElement('i', { 'data-dot': color }) }));
vi.mock('../src/components/AlertBanner', () => ({ AlertBanner: ({ lead, detail }) => React.createElement('div', { role: 'alert' }, `${lead} | ${detail}`) }));
vi.mock('../src/hooks/useAttention', () => ({ useAttention: () => ({ att: h.att, refresh: vi.fn() }) }));
vi.mock('../src/features/profile/PanelHeader', () => ({ PanelHeader: ({ right }) => React.createElement('header', {}, right) }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => vi.fn() }));
vi.mock('../src/hooks/useDaemonData', () => ({ useScheduleList: () => ({ data: { jobs: h.jobs }, refresh: vi.fn() }) }));
vi.mock('../src/hooks/usePullRefresh', () => ({ usePullRefresh: () => ({}) }));
vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call }) }));

import ScheduleList from '../app/profile/[id]/schedule/index.jsx';
import ScheduleJob from '../app/profile/[id]/schedule/[job].jsx';

beforeEach(() => {
  h.push.mockClear();
  h.call.mockClear();
  h.alert.mockClear();
});

describe('schedule list', () => {
  it('opens the page of the job a notification named', () => {
    h.params = { id: 'abby', job: 'j-mail' };
    render(<ScheduleList />);
    expect(h.push).toHaveBeenCalledWith({ pathname: '/profile/abby/schedule/[job]', params: { job: 'j-mail' } });
  });

  it('says when each job runs in words and marks a failed last run', () => {
    h.params = { id: 'abby' };
    render(<ScheduleList />);
    expect(screen.queryByText('every Monday at 06:00')).toBeNull();
    expect(screen.getByText('failed').getAttribute('data-color')).toBe('#a00');
    expect(h.push).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('First, every Monday at 06:00'));
    expect(h.push).toHaveBeenCalledWith({ pathname: '/profile/abby/schedule/[job]', params: { job: 'j-first' } });
  });
});

const NEXT = new Date(Date.now() + 2 * 86400000 + 60000).toISOString();
const base = h.jobs.slice();

describe('schedule list as the board draws it', () => {
  const fleet = [
    { id: 'a', kind: 'cron', expression: '0 6 * * 1', title: 'Weekly listing refresh', description: 'Compares every hotel listing', next_fire: NEXT },
    { id: 'b', kind: 'cron', expression: '30 7 * * *', title: 'Daily review digest', description: 'Summarises reviews', last_run_status: 'error', last_run_at: '2026-10-03T07:30:00Z', next_fire: NEXT },
    { id: 'c', kind: 'cron', expression: '0 9 * * 1', title: 'Nudge', paused: true },
    { id: 'd', kind: 'cron', expression: '0 8 * * 1', prompt: 'Fallback line\nsecond', next_fire: NEXT },
  ];

  beforeEach(() => { h.params = { id: 'abby' }; h.jobs = fleet; h.att = null; });
  afterEach(() => { h.jobs = base; h.att = null; });

  it('groups under Needs you, Active and Paused with counts, in that order', () => {
    const { container } = render(<ScheduleList />);
    const headings = [...container.querySelectorAll('h2')].map((n) => n.textContent);
    expect(headings).toEqual(['Needs you · 1', 'Active · 2', 'Paused · 1']);
  });

  it('shows title, one-line description and the next run, never a cron string', () => {
    const { container } = render(<ScheduleList />);
    expect(screen.getByText('Compares every hotel listing')).toBeTruthy();
    expect(screen.getAllByText('in 2d').length).toBe(2);
    expect(screen.getByText('paused')).toBeTruthy();
    expect(screen.getByText('Fallback line')).toBeTruthy();
    expect(container.textContent).not.toMatch(/\* \*/);
    expect(container.textContent).not.toMatch(/0 6/);
  });

  it('draws no empty line for a job without a description', () => {
    render(<ScheduleList />);
    const row = screen.getByLabelText(/^Nudge,/);
    expect(row.querySelectorAll('span').length).toBe(2);
  });

  it('colours the dot and the word by state and keeps every row at 44', () => {
    render(<ScheduleList />);
    const dots = [...document.querySelectorAll('[data-dot]')].map((n) => n.getAttribute('data-dot'));
    expect(dots).toEqual(['#f00', '#000', '#000', '#999']);
    expect(screen.getByText('failed').getAttribute('data-color')).toBe('#a00');
    for (const b of document.querySelectorAll('button')) expect(Number(b.getAttribute('data-minheight'))).toBeGreaterThanOrEqual(44);
  });
});

describe('schedule job page as the board draws it', () => {
  const job = { id: 'j-mail', kind: 'cron', expression: '30 7 * * *', prompt: 'mail prompt', title: 'Mail', description: 'Digest of the inbox', last_run_at: '2026-10-03T07:30:00Z', last_run_status: 'error', last_run_message: 'smtp refused', last_ok_at: '2026-10-02T07:30:00Z', next_fire: NEXT };
  beforeEach(() => { h.params = { id: 'abby', job: 'j-mail' }; h.jobs = [job]; h.att = null; });
  afterEach(() => { h.jobs = base; h.att = null; });

  it('opens on the failure banner and lays out ABOUT, WHEN, NEXT, LAST RUN, RUNS, NOTIFY, PROMPT', () => {
    const { container } = render(<ScheduleJob />);
    expect(screen.getByRole('alert').textContent).toMatch(/^Last run failed \| smtp refused\. Last good run:/);
    expect(container.firstChild.querySelector('[role=alert]')).toBeTruthy();
    const text = container.textContent;
    const order = ['ABOUT', 'WHEN', 'NEXT', 'LAST RUN', 'RUNS', 'NOTIFY', 'PROMPT'].map((l) => text.indexOf(l));
    expect(order.every((n) => n >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(screen.getByText('Digest of the inbox')).toBeTruthy();
    expect(screen.getByText(/^every day at 07:30/)).toBeTruthy();
    expect(screen.getByText('30 7 * * *')).toBeTruthy();
  });

  it('prefers the attention item over the job fields for the banner', () => {
    h.att = { schedules: [{ id: 'j-mail', message: 'imap down', last_ok_at: null }] };
    render(<ScheduleJob />);
    expect(screen.getByRole('alert').textContent).toMatch(/imap down\. It has not succeeded yet\./);
  });

  it('agrees between page and list for a failed job without a last run timestamp', () => {
    const bare = { ...job, last_run_at: undefined, last_ok_at: undefined };
    h.jobs = [bare];
    const page = render(<ScheduleJob />);
    expect(screen.getByRole('alert').textContent).toMatch(/^Last run failed \| smtp refused\. It has not succeeded yet\./);
    page.unmount();
    const list = render(<ScheduleList />);
    expect([...list.container.querySelectorAll('h2')].map((n) => n.textContent)).toEqual(['Needs you · 1']);
  });

  it('omits ABOUT without a description and shows no banner for a healthy job', () => {
    h.jobs = [{ ...job, description: undefined, last_run_status: 'ok', last_run_message: undefined }];
    const { container } = render(<ScheduleJob />);
    expect(container.textContent).not.toContain('ABOUT');
    expect(screen.queryByRole('alert')).toBeNull();
  });
});

describe('schedule job page', () => {
  it('leads with status and words, keeps the cron as a fact and shows a broken timeout', () => {
    h.params = { id: 'abby', job: 'j-mail' };
    render(<ScheduleJob />);
    expect(screen.getByText('every day at 07:30')).toBeTruthy();
    expect(screen.getByText('30 7 * * *')).toBeTruthy();
    expect(screen.getByText('PROMPT')).toBeTruthy();
    expect(screen.getByText("'timeout' must be a whole number of seconds").getAttribute('data-color')).toBe('#a00');
    expect(screen.getByText('mail prompt')).toBeTruthy();
  });

  it('runs and pauses from the page and deletes after a plain confirmation', async () => {
    h.params = { id: 'abby', job: 'j-mail' };
    render(<ScheduleJob />);
    fireEvent.click(screen.getByText('Run now'));
    expect(h.call).toHaveBeenCalledWith('host.schedule.fire', { profile: 'abby', id: 'j-mail' });
    fireEvent.click(screen.getByText('Pause'));
    expect(h.call).toHaveBeenCalledWith('host.schedule.set_paused', { profile: 'abby', id: 'j-mail', paused: true });
    fireEvent.click(screen.getByLabelText('More'));
    vi.useFakeTimers();
    fireEvent.click(screen.getByText('Delete'));
    vi.runAllTimers();
    vi.useRealTimers();
    expect(h.alert).toHaveBeenCalledTimes(1);
    expect(h.alert.mock.calls[0][0]).toBe('Delete "Mail"?');
  });

  it('says the job is gone when it no longer exists', () => {
    h.params = { id: 'abby', job: 'j-deleted' };
    render(<ScheduleJob />);
    expect(screen.getByText('This job is gone.')).toBeTruthy();
  });
});

describe('schedule job page when the schedule cannot load', () => {
  it('says the load failed and offers a retry instead of calling the job gone', async () => {
    vi.resetModules();
    vi.doMock('../src/hooks/useDaemonData', () => ({ useScheduleList: () => ({ data: null, loading: false, error: new Error('daemon unreachable'), refresh: vi.fn() }) }));
    vi.doMock('../src/components/LoadFailed', () => ({ LoadFailed: ({ label }) => React.createElement('div', { 'data-load-failed': label }) }));
    const { default: Page } = await import('../app/profile/[id]/schedule/[job].jsx');
    h.params = { id: 'abby', job: 'j-mail' };
    const { container } = render(<Page />);
    expect(container.querySelector('[data-load-failed="this job"]')).toBeTruthy();
    expect(screen.queryByText('This job is gone.')).toBeNull();
    vi.doUnmock('../src/hooks/useDaemonData');
    vi.doUnmock('../src/components/LoadFailed');
  });
});
