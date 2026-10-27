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
  role: 'admin',
  endpointId: 'c1',
  confirm: null,
  flat: (style) => [style].flat(Infinity).filter(Boolean).reduce((acc, x) => ({ ...acc, ...x }), {}),
}));

vi.mock('../src/components/EmptyState', async () => {
  const R = await import('react');
  return { EmptyState: ({ title, detail, action }) => R.createElement('div', null, R.createElement('span', null, title), R.createElement('span', null, detail), action ? R.createElement('button', { onClick: action.onPress }, action.label) : null) };
});
vi.mock('react-native', () => {
  const View = ({ children, accessibilityRole, accessibilityLabel }) => React.createElement('div', { role: accessibilityRole, 'aria-label': accessibilityLabel }, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-style': JSON.stringify(h.flat(style)) }, children);
  const Pressable = ({ children, onPress, accessibilityLabel, accessibilityRole, accessibilityState, accessibilityHint, disabled, style, hitSlop }) =>
    React.createElement('button', {
      type: 'button',
      onClick: disabled ? undefined : onPress,
      'aria-label': accessibilityLabel,
      'aria-expanded': accessibilityState?.expanded,
      'aria-selected': accessibilityState?.selected,
      'aria-busy': accessibilityState?.busy,
      'data-role': accessibilityRole,
      'data-hint': accessibilityHint,
      'data-hit': hitSlop ? JSON.stringify(hitSlop) : undefined,
      'data-style': JSON.stringify(h.flat(typeof style === 'function' ? style({ pressed: false }) : style)),
      disabled,
    }, typeof children === 'function' ? children({ pressed: false }) : children);
  const ScrollView = ({ children, stickyHeaderIndices, horizontal }) =>
    React.createElement('div', { 'data-sticky': stickyHeaderIndices ? JSON.stringify(stickyHeaderIndices) : undefined, 'data-horizontal': horizontal ? 'y' : undefined }, children);
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
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call, endpoint: { id: h.endpointId } }) }));
vi.mock('../src/hooks/useActiveRole', () => ({ useActiveRole: () => h.role }));
vi.mock('../src/components/ConfirmProvider', () => ({ useConfirm: () => h.confirm }));
vi.mock('../src/components/Expand', () => ({ Expand: ({ open, children }) => (open ? React.createElement('div', { 'data-expand': 'open' }, children) : null) }));
vi.mock('../src/components/LoadFailed', () => ({ LoadFailed: ({ label, onRetry }) => React.createElement('div', { role: 'alert' }, React.createElement('span', {}, `Couldn't load ${label}`), React.createElement('button', { type: 'button', onClick: onRetry }, 'Retry')) }));
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
      colors: { bg: '#fff', bgPane: '#fff', ink: '#000', ink2: '#333', ink3: '#666', accent: '#a70', warning: '#e08a3c', warningText: '#8a5a0a', danger: '#c14545', dangerText: '#b73737', selected: '#eee', line: '#ddd', line2: '#ccc', ink4: '#999', hover: '#f4f4f4' },
      fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoMedium: 'mm' },
      chromeScale: 1.3,
      fontSizes: tokens.fontSizes,
    }),
  };
});

import ActivityScreen from '../app/activity';
import { ACTIVITY_FILTERS } from '../src/features/shell/activityFeed';
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
  h.role = 'admin';
  h.endpointId = 'c1';
  h.confirm = vi.fn(async () => true);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const at = (s) => new Date((NOW + s) * 1000).toISOString();
const FLEET = {
  ...FULL,
  scheduled: [
    ...FULL.scheduled,
    { profile: 'doc', job_id: 'j3', title: 'doc · digest', next_fire: at(3600), last_run_at: NOW - 600, last_run_status: 'error', last_ok_at: NOW - 7200 },
    { profile: 'builder', job_id: 'b1', title: 'nightly sync', next_fire: at(9000), last_run_at: NOW - 90, last_run_status: 'error' },
    { profile: 'builder', job_id: 'b2', title: 'old failure', next_fire: null, last_run_at: NOW - 3 * 86400, last_run_status: 'error' },
    { profile: 'doc', job_id: 'soon', title: 'soon', next_fire: at(600), last_run_status: 'ok' },
    { profile: 'doc', job_id: 'late', title: 'overdue', next_fire: at(-60), last_run_status: 'ok' },
  ],
};

const heads = () => [...document.querySelectorAll('h2')].map((n) => n.textContent);
const chips = () => [...document.querySelectorAll('[data-role="radio"]')];
const chip = (name) => screen.getByLabelText(new RegExp(`^${name}, \\d+$`));
const style = (node) => JSON.parse(node.getAttribute('data-style'));

describe('activity screen', () => {
  it('leads with what needs the user, then failures, what runs and what is upcoming', () => {
    render(<ActivityScreen />);
    expect(heads()).toEqual(['Needs you · 2', 'Failing · 1', 'Running · 2', 'Upcoming · 1', 'Today']);
  });

  it('shows the shared grouping: failures leave Needs you and past runs leave Upcoming', () => {
    h.activity = state(FLEET);
    render(<ActivityScreen />);
    expect(heads()).toEqual(['Needs you · 2', 'Failing · 3', 'Running · 2', 'Upcoming · 2', 'Today']);
    expect(screen.queryByLabelText(/overdue/)).toBeNull();
    expect(screen.queryByLabelText(/old failure/)).toBeNull();
    expect(screen.queryByLabelText(/Run again/)).toBeNull();
  });

  it('puts a count on every filter that has entries, speaks it, and paints Failing in danger', () => {
    h.activity = state(FLEET);
    render(<ActivityScreen />);
    expect(chips().map((n) => n.getAttribute('aria-label'))).toEqual(['All, 9', 'Needs you, 2', 'Failing, 3', 'Running, 2', 'Upcoming, 2']);
    expect(ACTIVITY_FILTERS).toHaveLength(5);
    const count = (name) => [...chip(name).querySelectorAll('span')].at(-1);
    expect(style(count('Failing')).color).toBe('#b73737');
    expect(style(count('Running')).color).toBe('#666');
    expect(chip('All').getAttribute('aria-selected')).toBe('true');
  });

  it('shows only the chips that have entries, and none when one kind holds everything', () => {
    h.activity = state({ needsYou: [], running: FULL.running, scheduled: [FULL.scheduled[0]] });
    render(<ActivityScreen />);
    expect(chips().map((n) => n.getAttribute('aria-label'))).toEqual(['All, 3', 'Running, 2', 'Upcoming, 1']);
    cleanup();
    h.activity = state({ needsYou: [], running: [], scheduled: [FULL.scheduled[0]] });
    render(<ActivityScreen />);
    expect(chips()).toHaveLength(0);
  });

  it('filters to one section and says so when that section is empty', () => {
    render(<ActivityScreen />);
    fireEvent.click(chip('Running'));
    expect(heads()).toEqual(['Running · 2']);
    expect(chip('Running').getAttribute('aria-selected')).toBe('true');
    expect(chip('All').getAttribute('aria-selected')).toBe('false');
    fireEvent.click(chip('Upcoming'));
    expect(heads()).toEqual(['Upcoming · 1', 'Today']);
    h.activity = state({ needsYou: [], running: [], scheduled: [FULL.scheduled[0]] });
    cleanup();
    render(<ActivityScreen />);
    expect(chips()).toHaveLength(0);
  });

  it('keeps the chips fixed above a scroller that pins every section header', () => {
    h.activity = state(FLEET);
    render(<ActivityScreen />);
    const scroller = document.querySelector('[data-sticky]');
    expect(document.querySelector('[data-horizontal="y"]')).not.toBeNull();
    expect(scroller.contains(chip('All'))).toBe(false);
    const kids = [...scroller.children];
    const pinned = JSON.parse(scroller.getAttribute('data-sticky'));
    expect(pinned).toHaveLength(4);
    expect(pinned.map((i) => kids[i].textContent.split(' · ')[0])).toEqual(['Needs you', 'Failing', 'Running', 'Upcoming']);
    expect(kids[pinned[0]].getAttribute('role')).toBe('header');
  });

  it('says the calm state when nothing needs the user, and keeps Running and Upcoming', () => {
    h.activity = state({ needsYou: [], running: FULL.running, scheduled: [FULL.scheduled[0]] });
    render(<ActivityScreen />);
    expect(screen.getByText(/^Nothing needs you · next daily brief, today \d{2}:\d{2}$/)).toBeTruthy();
    expect(heads()).toEqual(['Running · 2', 'Upcoming · 1', 'Today']);
  });

  it('names a later next run by its weekday or date, lowercasing only today and tomorrow', () => {
    const later = { profile: 'doc', job_id: 'far', title: 'far run', next_fire: new Date((NOW + 4 * 86400) * 1000).toISOString(), last_run_status: 'ok' };
    h.activity = state({ needsYou: [], running: FULL.running, scheduled: [later] });
    render(<ActivityScreen />);
    expect(screen.getByText(/^Nothing needs you · next far run, [A-Z][a-z]{2} \d{1,2} [A-Z][a-z]{2} \d{2}:\d{2}$/)).toBeTruthy();
  });

  it('says only that nothing needs you when no run is upcoming', () => {
    h.activity = state({ needsYou: [], running: FULL.running, scheduled: [] });
    render(<ActivityScreen />);
    expect(screen.getByText('Nothing needs you now')).toBeTruthy();
  });

  it('shows ten upcoming runs and reveals the rest behind Show more', () => {
    const scheduled = Array.from({ length: 14 }, (_, i) => ({ profile: 'a', job_id: `j${i}`, title: `job ${i}`, next_fire: new Date((NOW + 60 * (i + 1)) * 1000).toISOString(), last_run_status: 'ok' }));
    h.activity = state({ needsYou: [], running: FULL.running, scheduled });
    render(<ActivityScreen />);
    expect(screen.getAllByLabelText(/a · job \d+/)).toHaveLength(10);
    expect(heads()).toContain('Upcoming · 14');
    fireEvent.click(screen.getByLabelText('Show 4 more upcoming'));
    expect(screen.getAllByLabelText(/a · job \d+/)).toHaveLength(14);
    expect(screen.queryByLabelText(/more upcoming$/)).toBeNull();
  });

  it('has no Show more at ten upcoming runs', () => {
    const scheduled = Array.from({ length: 10 }, (_, i) => ({ profile: 'a', job_id: `j${i}`, title: `job ${i}`, next_fire: new Date((NOW + 60 * (i + 1)) * 1000).toISOString(), last_run_status: 'ok' }));
    h.activity = state({ needsYou: [], running: FULL.running, scheduled });
    render(<ActivityScreen />);
    expect(screen.queryByLabelText(/more upcoming$/)).toBeNull();
  });

  it('groups failures per profile, the latest first and expanded, the rest one collapsed line', () => {
    h.activity = state(FLEET);
    render(<ActivityScreen />);
    const groups = [...document.querySelectorAll('button[aria-expanded]')];
    expect(groups.map((g) => g.getAttribute('aria-label'))).toEqual([
      'builder, 1 failing job, latest 2m ago, expanded',
      'doc, 2 failing jobs, latest 10m ago, collapsed',
    ]);
    expect(screen.queryByLabelText(/^nightly sync, failed/)).not.toBeNull();
    expect(screen.queryByLabelText(/^digest, failed/)).toBeNull();
    fireEvent.click(groups[1]);
    expect(screen.getByLabelText('doc, 2 failing jobs, latest 10m ago, expanded').getAttribute('aria-expanded')).toBe('true');
    expect(screen.queryByLabelText(/^digest, failed/)).not.toBeNull();
    expect(screen.queryByLabelText(/^weekly labs, failed/)).not.toBeNull();
    fireEvent.click(screen.getByLabelText(/^builder, 1 failing job/));
    expect(screen.queryByLabelText(/^nightly sync, failed/)).toBeNull();
  });

  it('drops the profile prefix from a job title, puts failed in red alone and last ok only when sent', () => {
    h.activity = state(FLEET);
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText(/^doc, 2 failing jobs/));
    const digest = screen.getByLabelText('digest, failed 10m ago, last ok 2h ago');
    const meta = digest.querySelectorAll('span')[1];
    expect(meta.textContent).toBe('failed 10m ago · last ok 2h ago');
    expect(style(meta.querySelector('span')).color).toBe('#b73737');
    expect(style(meta).color).toBe('#666');
    expect(screen.getByLabelText('weekly labs, failed 1h ago')).toBeTruthy();
    expect(screen.getByLabelText('nightly sync, failed 2m ago').getAttribute('data-hint')).toBe('Opens the job');
  });

  it('opens a failing job on its schedule page, replacing the detail pane on two panes', () => {
    h.activity = state(FLEET);
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText(/^nightly sync, failed/));
    expect(h.push).toHaveBeenCalledWith('/profile/builder/schedule/b1');
    h.twoPane = true;
    cleanup();
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText(/^nightly sync, failed/));
    expect(h.replace).toHaveBeenCalledWith('/profile/builder/schedule/b1');
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

  it('opens an upcoming job on its page', () => {
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText(/^doc · daily brief, in 2h/));
    expect(h.push).toHaveBeenCalledWith('/profile/doc/schedule/j1');
  });

  it('says nothing is running once the list is empty, and hides the filters', () => {
    h.activity = state({ needsYou: [], running: [], scheduled: [] });
    render(<ActivityScreen />);
    expect(screen.getByText('Nothing running')).toBeTruthy();
    expect(chips()).toHaveLength(0);
  });

  it('says the daemon is too old instead of pretending nothing runs', () => {
    h.activity = state({ needsYou: [], running: [], scheduled: [] }, { supported: false, unsupported: true });
    render(<ActivityScreen />);
    expect(screen.getByText('Activity needs a newer daemon')).toBeTruthy();
  });

  it('offers a retry when the first list could not be loaded, instead of staying blank', () => {
    const retry = vi.fn();
    h.activity = state({ needsYou: [], running: [], scheduled: [] }, { supported: false, loadError: new Error('timeout'), refresh: retry });
    render(<ActivityScreen />);
    expect(screen.getByText("Couldn't load activity")).toBeTruthy();
    expect(screen.queryByText('Nothing running')).toBeNull();
    fireEvent.click(screen.getByText('Retry'));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it('shows neither message while the first list is still loading', () => {
    h.activity = state({ needsYou: [], running: [], scheduled: [] }, { supported: false });
    render(<ActivityScreen />);
    expect(screen.queryByText('Nothing running')).toBeNull();
    expect(screen.queryByText('Activity needs a newer daemon')).toBeNull();
  });
});

describe('retrying failed jobs', () => {
  const forbidden = () => Object.assign(new Error('forbidden'), { code: -32601 });

  it('offers Retry to admins only, as a 44 pt target beside the row', () => {
    h.activity = state(FLEET);
    render(<ActivityScreen />);
    const retry = screen.getByLabelText('Retry nightly sync');
    expect(style(retry)).toMatchObject({ minHeight: 44, minWidth: 44 });
    expect(screen.getByLabelText('Retry all 3 failing jobs')).toBeTruthy();
    cleanup();
    h.role = 'member';
    render(<ActivityScreen />);
    expect(screen.queryByLabelText(/^Retry /)).toBeNull();
    expect(screen.queryByLabelText(/^Retry all/)).toBeNull();
    cleanup();
    h.role = null;
    render(<ActivityScreen />);
    expect(screen.queryByLabelText(/^Retry /)).toBeNull();
    h.role = 'admin';
  });

  it('fires the job from Retry without opening it, then refreshes', async () => {
    h.activity = state(FLEET);
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText('Retry nightly sync'));
    expect(h.call).toHaveBeenCalledWith('host.schedule.fire', { profile: 'builder', id: 'b1' });
    expect(h.push).not.toHaveBeenCalled();
    await waitFor(() => expect(h.refresh).toHaveBeenCalled());
    expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ kind: 'success' }));
  });

  it('tells the user when Retry fails and keeps the button', async () => {
    h.activity = state(FLEET);
    h.call = vi.fn(async () => { throw new Error('daemon unreachable'); });
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText('Retry nightly sync'));
    await waitFor(() => expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ kind: 'danger', message: 'daemon unreachable' })));
    await waitFor(() => expect(screen.getByLabelText('Retry nightly sync').disabled).toBe(false));
  });

  it('starts one run for a double tap and frees the button once it settles', async () => {
    h.activity = state(FLEET);
    let release;
    h.call = vi.fn(() => new Promise((resolve) => { release = resolve; }));
    render(<ActivityScreen />);
    const btn = screen.getByLabelText('Retry nightly sync');
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(h.call).toHaveBeenCalledTimes(1);
    expect(btn.getAttribute('aria-busy')).toBe('true');
    await act(async () => { release({ ok: true }); });
    await waitFor(() => expect(screen.getByLabelText('Retry nightly sync').disabled).toBe(false));
  });

  it('hides Retry for good after forbidden, until the connection changes', async () => {
    h.activity = state(FLEET);
    h.call = vi.fn(async () => { throw forbidden(); });
    const { rerender } = render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText('Retry nightly sync'));
    await waitFor(() => expect(screen.queryByLabelText(/^Retry /)).toBeNull());
    expect(screen.queryByLabelText(/^Retry all/)).toBeNull();
    expect(h.toast).not.toHaveBeenCalled();
    rerender(<ActivityScreen />);
    expect(screen.queryByLabelText(/^Retry /)).toBeNull();
    h.endpointId = 'c2';
    rerender(<ActivityScreen />);
    await waitFor(() => expect(screen.queryByLabelText('Retry nightly sync')).not.toBeNull());
    h.endpointId = 'c1';
  });

  it('asks before Retry all and starts nothing when the user cancels', async () => {
    h.activity = state(FLEET);
    h.confirm = vi.fn(async () => false);
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText('Retry all 3 failing jobs'));
    await waitFor(() => expect(h.confirm).toHaveBeenCalled());
    expect(h.confirm.mock.calls[0][0]).toMatchObject({ title: 'Retry 3 jobs?', confirmLabel: 'Retry all', typed: false });
    expect(h.confirm.mock.calls[0][0].body).toMatch(/one agent run per job.*costs money/);
    expect(h.call).not.toHaveBeenCalled();
  });

  it('fires every failing job in order once confirmed, then reports the count', async () => {
    h.activity = state(FLEET);
    h.confirm = vi.fn(async () => true);
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText('Retry all 3 failing jobs'));
    await waitFor(() => expect(h.toast).toHaveBeenCalledWith({ message: 'Retrying 3 jobs', kind: 'success' }));
    expect(h.call.mock.calls.map(([, p]) => `${p.profile}/${p.id}`)).toEqual(['builder/b1', 'doc/j3', 'doc/j2']);
    expect(h.refresh).toHaveBeenCalled();
  });

  it('stops Retry all at the first forbidden and hides Retry', async () => {
    h.activity = state(FLEET);
    h.confirm = vi.fn(async () => true);
    h.call = vi.fn(async () => { throw forbidden(); });
    render(<ActivityScreen />);
    fireEvent.click(screen.getByLabelText('Retry all 3 failing jobs'));
    await waitFor(() => expect(screen.queryByLabelText(/^Retry all/)).toBeNull());
    expect(h.call).toHaveBeenCalledTimes(1);
    expect(h.toast).not.toHaveBeenCalled();
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

  it('names the default profile alpi on every kind of row, as the chat does', () => {
    const base = { title: 'digest', job_id: 'j9', next_fire: new Date((NOW + 7200) * 1000).toISOString(), last_run_at: NOW - 3600, last_run_status: 'error' };
    const sections = activitySections({
      needsYou: [{ kind: 'approval', request_id: 'r9', profile: 'default', title: 'a command', ts: NOW - 5 }],
      running: [{ kind: 'turn', profile: 'default', title: 'summary', started_at: NOW - 5, source: 'chat' }],
      scheduled: [{ ...base, profile: 'default' }],
    }, NOW);
    const titles = sections.flatMap((sec) => (sec.rows ?? sec.groups.flatMap((g) => g.rows)).map((r) => r.title));
    expect(titles.length).toBeGreaterThan(3);
    expect(titles.every((t) => t.startsWith('alpi · '))).toBe(true);
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

  it('formats elapsed and remaining time on one scale', () => {
    expect(ago(NOW - 12, NOW)).toBe('12s ago');
    expect(ago(NOW - 3 * 86400, NOW)).toBe('3d ago');
    expect(until(NOW + 300, NOW)).toBe('in 5m');
    expect(until(NOW - 5, NOW)).toBe('due now');
    expect(until(null, NOW)).toBe('');
  });
});
