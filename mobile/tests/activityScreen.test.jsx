import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

const h = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  focus: vi.fn(),
  refresh: vi.fn(async () => {}),
  twoPane: false,
  activity: null,
}));

vi.mock('react-native', () => {
  const View = ({ children, accessibilityRole }) => React.createElement('div', { role: accessibilityRole }, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, accessibilityLabel, disabled }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, disabled }, children);
  const ScrollView = ({ children }) => React.createElement('div', {}, children);
  return { View, Text, Pressable, ScrollView, RefreshControl: () => null };
});

vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, replace: h.replace }),
  usePathname: () => '/activity',
  useFocusEffect: () => {},
}));
vi.mock('../src/components/ScreenHeader', () => ({ ScreenHeader: ({ title }) => React.createElement('h1', {}, title) }));
vi.mock('../src/hooks/useDaemonData', () => ({ useProfileSummaries: () => ({ data: { profiles: [{ name: 'doc', fold: 'heart', accent: '#f36a8a' }] } }) }));
vi.mock('../src/components/Fold', () => ({ Fold: ({ fold, pulse }) => React.createElement('i', { 'data-fold': fold ?? 'none', 'data-pulse': String(!!pulse) }) }));
vi.mock('../src/components/Icon', () => ({ Icon: ({ name }) => React.createElement('i', { 'data-icon': name }) }));
vi.mock('../src/components/Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('h2', {}, children) }));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => vi.fn() }));
vi.mock('../src/hooks/usePullRefresh', () => ({ usePullRefresh: () => ({ refreshing: false, onRefresh: vi.fn() }) }));
vi.mock('../src/hooks/useRequestQueue', () => ({ focusRequest: h.focus }));
vi.mock('../src/nav/PaneContext', () => ({ usePane: () => ({ twoPane: h.twoPane }) }));
vi.mock('../src/hooks/useActivity', async (importOriginal) => ({
  ...(await importOriginal()),
  useActivity: () => h.activity,
}));
vi.mock('../src/theme/ThemeContext', async () => {
  const tokens = await import('../src/theme/tokens');
  return {
    useTheme: () => ({
      colors: { bg: '#fff', bgPane: '#fff', ink: '#000', ink2: '#333', ink3: '#666', accent: '#a70', warning: '#e08a3c', warningText: '#8a5a0a', danger: '#c14545', dangerText: '#b73737', selected: '#eee' },
      fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

import ActivityScreen from '../app/activity';
import { activitySections, ago, until } from '../src/features/shell/ActivityList';

const NOW = Date.now() / 1000;

const FULL = {
  needsYou: [
    { kind: 'approval', request_id: 'r1', profile: 'builder', title: 'run a shell command', ts: NOW - 12, timeout_s: 60 },
    { kind: 'clarification', request_id: 'q1', profile: 'doc', title: 'Which hotel first?', ts: NOW - 90 },
  ],
  running: [
    { kind: 'turn', profile: 'alpi', session_id: 's 1', title: 'deploy summary', started_at: NOW - 42, source: 'chat' },
    { kind: 'workgroup', profile: 'alpi', workgroup_id: 'launch-crew', name: 'launch-crew', phase: 'analyze', phases_done: 2, phases_total: 4 },
  ],
  scheduled: [
    { profile: 'doc', job_id: 'j1', title: 'daily brief', next_fire: new Date((NOW + 7200) * 1000).toISOString(), last_run_status: 'ok' },
    { profile: 'doc', job_id: 'j2', title: 'weekly labs', next_fire: null, last_run_at: NOW - 3600, last_run_status: 'error' },
  ],
};

function state(activity, extra = {}) {
  return { activity, supported: true, unsupported: false, refresh: h.refresh, ...extra };
}

beforeEach(() => {
  h.push.mockClear();
  h.replace.mockClear();
  h.focus.mockClear();
  h.twoPane = false;
  h.activity = state(FULL);
});
afterEach(cleanup);

describe('activity screen', () => {
  it('leads with what needs the user, then what runs, then what is scheduled', () => {
    render(<ActivityScreen />);
    const heads = [...document.querySelectorAll('h2')].map((n) => n.textContent);
    expect(heads).toEqual(['Needs you · 2', 'Running · 2', 'Scheduled']);
  });

  it('leads each row with the profile object, the workgroup with its honeycomb rippling while it runs', () => {
    render(<ActivityScreen />);
    const folds = [...document.querySelectorAll('[data-fold]')];
    expect(folds.some((n) => n.getAttribute('data-fold') === 'heart' && n.getAttribute('data-pulse') === 'false')).toBe(true);
    expect(folds.some((n) => n.getAttribute('data-fold') === 'honeycomb' && n.getAttribute('data-pulse') === 'true')).toBe(true);
  });

  it('opens the approval sheet and the question sheet from a needs-you row', () => {
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText(/^builder · run a shell command, approval · 1\ds ago, Review$/));
    expect(h.focus).toHaveBeenCalledWith('approval', 'r1');
    fireEvent.click(screen.getByLabelText(/^doc · Which hotel first\?, question/));
    expect(h.focus).toHaveBeenLastCalledWith('clarification', 'q1');
    expect(h.push).not.toHaveBeenCalled();
  });

  it('opens the running chat on its session and the workgroup on its phase', () => {
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText(/^alpi · deploy summary/));
    expect(h.push).toHaveBeenCalledWith('/chat/alpi?sid=s%201');
    fireEvent.click(screen.getByLabelText(/^launch-crew · #analyze, phase 2 of 4/));
    expect(h.push).toHaveBeenLastCalledWith('/wg/launch-crew');
  });

  it('replaces the detail pane instead of stacking on two panes', () => {
    h.twoPane = true;
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText(/^doc · weekly labs, failed 1h ago/));
    expect(h.replace).toHaveBeenCalledWith('/profile/doc/schedule');
  });

  it('says nothing is running once the list is empty', () => {
    h.activity = state({ needsYou: [], running: [], scheduled: [] });
    render(<ActivityScreen />);
    expect(screen.getByText('Nothing running')).toBeTruthy();
  });

  it('says the daemon is too old instead of pretending nothing runs', () => {
    h.activity = state({ needsYou: [], running: [], scheduled: [] }, { supported: false, unsupported: true });
    render(<ActivityScreen />);
    expect(screen.getByText('Activity needs a newer daemon')).toBeTruthy();
  });

  it('shows neither message while the first list is still loading', () => {
    h.activity = state({ needsYou: [], running: [], scheduled: [] }, { supported: false });
    render(<ActivityScreen />);
    expect(screen.queryByText('Nothing running')).toBeNull();
    expect(screen.queryByText('Activity needs a newer daemon')).toBeNull();
  });
});

describe('activity rows', () => {
  it('marks a recent failure and times the next run', () => {
    const [, , scheduled] = activitySections(FULL, NOW);
    expect(scheduled.rows.map((r) => [r.icon, r.sub])).toEqual([['clock', 'in 2h'], ['x', 'failed 1h ago']]);
  });

  it('formats elapsed and remaining time on one scale', () => {
    expect(ago(NOW - 12, NOW)).toBe('12s ago');
    expect(ago(NOW - 3 * 86400, NOW)).toBe('3d ago');
    expect(until(NOW + 300, NOW)).toBe('in 5m');
    expect(until(NOW - 5, NOW)).toBe('due now');
    expect(until(null, NOW)).toBe('');
  });
});
