import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  params: { id: 'abby', job: 'j-mail' },
  push: vi.fn(),
  call: vi.fn(async () => ({})),
  alert: vi.fn(),
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
  const Pressable = ({ children, onPress, accessibilityLabel }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel }, typeof children === 'function' ? children({ pressed: false }) : children);
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
    colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', danger: '#f00', dangerText: '#a00', hover: '#eee', selected: '#ddd' },
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
}));
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
    expect(screen.getByText('every Monday at 06:00')).toBeTruthy();
    expect(screen.getByText('every day at 07:30')).toBeTruthy();
    expect(screen.getByText('failed').getAttribute('data-color')).toBe('#a00');
    expect(h.push).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('First, every Monday at 06:00'));
    expect(h.push).toHaveBeenCalledWith({ pathname: '/profile/abby/schedule/[job]', params: { job: 'j-first' } });
  });
});

describe('schedule job page', () => {
  it('leads with status and words, keeps the cron as a fact and shows a broken timeout', () => {
    h.params = { id: 'abby', job: 'j-mail' };
    render(<ScheduleJob />);
    expect(screen.getByText('every day at 07:30')).toBeTruthy();
    expect(screen.getByText('30 7 * * *')).toBeTruthy();
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
