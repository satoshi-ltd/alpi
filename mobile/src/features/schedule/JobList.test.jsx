import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

const h = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
  state: { data: { jobs: [] }, loading: false, error: null },
  activity: { running: [] },
}));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, accessibilityLabel, style }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-bg': (typeof style === 'function' ? style({ pressed: false }) : style)?.backgroundColor }, typeof children === 'function' ? children({ pressed: false }) : children);
  return { View, Text, Pressable, ScrollView: ({ children }) => React.createElement('div', {}, children), RefreshControl: () => null };
});
vi.mock('expo-router', () => ({ useRouter: () => ({ push: h.push }) }));
vi.mock('../../components/Button', () => ({ Button: ({ title, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, title) }));
vi.mock('../../components/Dot', () => ({ Dot: ({ color, pulse }) => React.createElement('i', { 'data-dot': color, 'data-pulse': String(!!pulse) }) }));
vi.mock('../../components/Field', () => ({
  Field: ({ value, onChangeText, placeholder }) => React.createElement('input', { value, placeholder, 'aria-label': 'search', onChange: (e) => onChangeText(e.target.value) }),
}));
vi.mock('../../components/ListSkeleton', () => ({ ListSkeleton: () => React.createElement('div', {}, 'skeleton') }));
vi.mock('../../components/LoadFailed', () => ({
  LoadFailed: ({ label, error, onRetry }) => React.createElement('div', { role: 'alert' }, `Couldn't load ${label}: ${error}`, React.createElement('button', { type: 'button', onClick: onRetry }, 'Retry')),
}));
vi.mock('../../components/Row', () => ({
  Row: ({ label, helper }) => React.createElement('div', {}, `${label}|${helper}`),
  RowGroup: ({ children }) => React.createElement('div', {}, children),
  RowSeparator: () => null,
  SectionHeader: ({ children }) => React.createElement('h2', {}, children),
}));
vi.mock('../../hooks/useDaemonData', () => ({ useScheduleList: () => ({ ...h.state, refresh: h.refresh }) }));
vi.mock('../../hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../../hooks/usePullRefresh', () => ({ usePullRefresh: () => ({ refreshing: false, onRefresh: vi.fn() }) }));
vi.mock('../../hooks/useActivity', async (importOriginal) => ({ ...(await importOriginal()), useActivity: () => ({ activity: h.activity }) }));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', danger: '#f00', dangerText: '#a00', selected: '#ddd' },
      fonts: { sans: { regular: 'r', semibold: 's' }, mono: 'm' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

import { JobList } from './JobList';

const NOW = Date.now();
const NEXT = new Date(NOW + 20 * 3600_000).toISOString();
const JOBS = [
  { id: 'a', title: 'Weekly listing refresh', description: 'Compares every listing', kind: 'cron', expression: '0 6 * * 1', next_fire: NEXT, last_run_status: 'ok', last_run_at: new Date(NOW - 2 * 86400_000).toISOString() },
  { id: 'b', title: 'Daily review digest', kind: 'cron', expression: '30 7 * * *', next_fire: NEXT, last_run_status: 'error', last_run_at: new Date(NOW - 3600_000).toISOString(), last_run_message: 'timed out\nwhile reading' },
  { id: 'c', title: 'Nudge', kind: 'cron', expression: '0 9 * * 1', paused: true },
];

function mount(props = {}) {
  return render(<JobList profile="scout" onOpen={props.onOpen ?? vi.fn()} {...props} />);
}

beforeEach(() => {
  h.push.mockClear();
  h.refresh.mockClear();
  h.state = { data: { jobs: JOBS }, loading: false, error: null };
  h.activity = { running: [] };
});
afterEach(cleanup);

describe('job list', () => {
  it('puts the last result under every job, with the failure reason on one line', () => {
    mount();
    expect(screen.getByText('ran 2d ago')).toBeTruthy();
    expect(screen.getByText('failed 1h ago · timed out while reading')).toBeTruthy();
    expect(screen.getByText('never run')).toBeTruthy();
  });

  it('marks a running job with a pulsing dot and the time it started', () => {
    h.activity = { running: [{ kind: 'turn', profile: 'scout', job_id: 'a', started_at: NOW / 1000 - 90, source: 'schedule' }] };
    mount();
    const row = screen.getByLabelText(/^Weekly listing refresh,/);
    expect(row.getAttribute('aria-label')).toMatch(/, running$/);
    expect(row.querySelector('[data-pulse="true"]')).toBeTruthy();
    expect([...row.querySelectorAll('span')].map((n) => n.textContent)).toEqual(['Weekly listing refresh', 'running', 'Compares every listing', expect.stringMatching(/^started \d{2}:\d{2}$/)]);
    expect(document.querySelectorAll('[data-pulse="true"]').length).toBe(1);
  });

  it('ignores a run of another profile', () => {
    h.activity = { running: [{ kind: 'turn', profile: 'other', job_id: 'a', started_at: NOW / 1000 - 5, source: 'schedule' }] };
    mount();
    expect(document.querySelectorAll('[data-pulse="true"]').length).toBe(0);
  });

  it('filters on the title, the description, the prompt, the id and what it says about when', () => {
    mount();
    const search = screen.getByLabelText('search');
    fireEvent.change(search, { target: { value: 'compares' } });
    expect(screen.queryByLabelText(/^Daily review digest/)).toBeNull();
    expect(screen.getByLabelText(/^Weekly listing refresh/)).toBeTruthy();
    fireEvent.change(search, { target: { value: 'every day at 07:30' } });
    expect(screen.getByLabelText(/^Daily review digest/)).toBeTruthy();
    expect(screen.queryByLabelText(/^Weekly listing refresh/)).toBeNull();
    fireEvent.change(search, { target: { value: 'zzz' } });
    expect(screen.getByText('No matches|Try a different query, or clear it.')).toBeTruthy();
  });

  it('opens a job and shades the selected one', () => {
    const onOpen = vi.fn();
    mount({ onOpen, selectedId: 'b' });
    fireEvent.click(screen.getByLabelText(/^Weekly listing refresh/));
    expect(onOpen).toHaveBeenCalledWith('a');
    expect(screen.getByLabelText(/^Daily review digest/).getAttribute('data-bg')).toBe('#ddd');
    expect(screen.getByLabelText(/^Weekly listing refresh/).getAttribute('data-bg')).toBe('transparent');
  });
});

describe('job list states', () => {
  it('shows the shared load-error card with a Retry that refetches', () => {
    h.state = { data: null, loading: false, error: new Error('daemon unreachable') };
    mount();
    expect(screen.getByRole('alert').textContent).toContain("Couldn't load schedule: daemon unreachable");
    fireEvent.click(screen.getByText('Retry'));
    expect(h.refresh).toHaveBeenCalled();
  });

  it('keeps the jobs it already has when a refresh fails', () => {
    h.state = { data: { jobs: JOBS }, loading: false, error: new Error('daemon unreachable') };
    mount();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByLabelText(/^Nudge/)).toBeTruthy();
  });

  it('offers New schedule on an empty list, opening the chat with the request half written', () => {
    h.state = { data: { jobs: [] }, loading: false, error: null };
    mount();
    expect(screen.getByText('No scheduled jobs|Ask the agent to set one up.')).toBeTruthy();
    expect(screen.queryByLabelText('search')).toBeNull();
    fireEvent.click(screen.getByText('New schedule'));
    expect(h.push).toHaveBeenCalledWith(`/chat/scout?draft=${encodeURIComponent('Schedule: ')}`);
  });

  it('shows a skeleton while the first load runs', () => {
    h.state = { data: null, loading: true, error: null };
    mount();
    expect(screen.getByText('skeleton')).toBeTruthy();
  });
});
