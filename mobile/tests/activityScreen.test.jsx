import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

const h = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  focus: vi.fn(),
  refresh: vi.fn(async () => {}),
  twoPane: false,
  activity: null,
  call: null,
  toast: null,
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
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call }) }));
vi.mock('../src/components/Toast', () => ({ useToast: () => h.toast }));
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

const NOW = (() => {
  const noon = new Date();
  noon.setHours(12, 0, 0, 0);
  return noon.getTime() / 1000;
})();

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
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(NOW * 1000);
  h.push.mockClear();
  h.replace.mockClear();
  h.focus.mockClear();
  h.twoPane = false;
  h.activity = state(FULL);
  h.call = vi.fn(async () => ({ ok: true }));
  h.toast = vi.fn();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('activity screen', () => {
  it('leads with what needs the user, then what runs, then what is scheduled', () => {
    render(<ActivityScreen />);
    const heads = [...document.querySelectorAll('h2')].map((n) => n.textContent);
    expect(heads).toEqual(['Needs you · 3', 'Running · 2', 'Next up · 2', 'Today', 'No fixed time']);
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
    fireEvent.click(screen.getByLabelText(/^doc · weekly labs, failed 1h ago$/));
    expect(h.replace).toHaveBeenCalledWith('/profile/doc/schedule/j2');
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
  it('puts a recent failure in Needs you and times the next runs under their day', () => {
    const [needs, , next] = activitySections(FULL, NOW);
    expect(needs.rows.map((r) => [r.icon, r.sub, r.action])).toEqual([['triangle-alert', 'approval · 12s ago', 'Review'], ['triangle-alert', 'question · 2m ago', 'Review'], ['x', 'failed 1h ago', 'Run again']]);
    expect(next.groups.map((g) => [g.label, g.rows.map((r) => [r.icon, r.sub])])).toEqual([
      ['Today', [['clock', 'in 2h']]],
      ['No fixed time', [['clock', 'not scheduled']]],
    ]);
  });

  it('groups what comes next by day with the time on the right, soonest first', () => {
    const day = 86400;
    const at = (s) => new Date((NOW + s) * 1000).toISOString();
    const [next] = activitySections({
      needsYou: [], running: [],
      scheduled: [
        { profile: 'a', job_id: 'x3', title: 'later', next_fire: at(3 * day), last_run_status: 'ok' },
        { profile: 'a', job_id: 'x1', title: 'soon', next_fire: at(600), last_run_status: 'ok' },
        { profile: 'a', job_id: 'x2', title: 'tomorrow', next_fire: at(day + 600), last_run_status: 'ok' },
      ],
    }, NOW);
    expect(next.label).toBe('Next up · 3');
    expect(next.groups.map((g) => [g.label, g.rows.map((r) => r.title)])).toEqual([
      ['Today', ['a · soon']],
      ['Tomorrow', ['a · tomorrow']],
      [next.groups[2].label, ['a · later']],
    ]);
    expect(next.groups[2].label).toMatch(/^[A-Z][a-z]{2} \d{1,2} [A-Z][a-z]{2}$/);
    expect(next.groups[0].rows[0].when).toMatch(/^\d{2}:\d{2}$/);
  });

  it('says how many rows are shown when the daemon capped the list', () => {
    const scheduled = Array.from({ length: 20 }, (_, i) => ({ profile: 'a', job_id: `j${i}`, title: `job ${i}`, next_fire: new Date((NOW + 60 * (i + 1)) * 1000).toISOString(), last_run_status: 'ok' }));
    expect(activitySections({ needsYou: [], running: [], scheduled }, NOW)[0].label).toBe('Next up · 20 shown');
  });

  it('opens a running scheduled job on its page, never on the chat of its profile', () => {
    h.activity = state({ needsYou: [], running: [{ kind: 'turn', profile: 'doc', title: 'Daily brief', started_at: NOW - 40, source: 'schedule', job_id: 'j1' }], scheduled: [] });
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText(/^doc · Daily brief, 40s · scheduled$/));
    expect(h.push).toHaveBeenCalledWith('/profile/doc/schedule/j1');
  });

  it('does not list a failed job as waiting while it runs again', () => {
    const rerun = { kind: 'turn', profile: 'doc', title: 'weekly labs', started_at: NOW - 5, source: 'schedule', job_id: 'j2' };
    const [needs] = activitySections({ ...FULL, needsYou: [], running: [rerun] }, NOW);
    expect(needs.key).toBe('running');
  });

  it('runs a failed job again from its own 44 pt target without opening it', async () => {
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText('Run again doc · weekly labs'));
    expect(h.call).toHaveBeenCalledWith('host.schedule.fire', { profile: 'doc', id: 'j2' });
    expect(h.push).not.toHaveBeenCalled();
    await waitFor(() => expect(h.refresh).toHaveBeenCalled());
  });

  it('tells the user when Run again fails', async () => {
    h.call = vi.fn(async () => { throw new Error('daemon unreachable'); });
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText('Run again doc · weekly labs'));
    await waitFor(() => expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ kind: 'danger', message: 'daemon unreachable' })));
  });

  it('starts one run for a double tap on Run again, and allows the next tap once it settles', async () => {
    let release;
    h.call = vi.fn(() => new Promise((resolve) => { release = resolve; }));
    render(<ActivityScreen />);
    const chip = screen.getByLabelText('Run again doc · weekly labs');
    fireEvent.click(chip);
    fireEvent.click(chip);
    expect(h.call).toHaveBeenCalledTimes(1);
    await act(async () => { release({ ok: true }); });
    await waitFor(() => expect(h.refresh).toHaveBeenCalled());
    fireEvent.click(chip);
    expect(h.call).toHaveBeenCalledTimes(2);
  });

  it('formats elapsed and remaining time on one scale', () => {
    expect(ago(NOW - 12, NOW)).toBe('12s ago');
    expect(ago(NOW - 3 * 86400, NOW)).toBe('3d ago');
    expect(until(NOW + 300, NOW)).toBe('in 5m');
    expect(until(NOW - 5, NOW)).toBe('due now');
    expect(until(null, NOW)).toBe('');
  });
});
