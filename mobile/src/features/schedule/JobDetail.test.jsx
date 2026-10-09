import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

const h = vi.hoisted(() => ({
  push: vi.fn(),
  call: null,
  toast: vi.fn(),
  jobs: [],
  activity: { running: [] },
  outputs: [],
  handlers: [],
  refresh: vi.fn(),
  copied: [],
}));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, accessibilityLabel, disabled }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, disabled }, typeof children === 'function' ? children({ pressed: false }) : children);
  const ScrollView = ({ children }) => React.createElement('div', {}, children);
  return { View, Text, Pressable, ScrollView, RefreshControl: () => null };
});
vi.mock('expo-router', () => ({ useRouter: () => ({ push: h.push }) }));
vi.mock('../../components/ActionSheet', () => ({
  ActionSheet: ({ open, actions }) => (open ? React.createElement('div', { role: 'menu' }, actions.map((a) => React.createElement('button', { key: a.id, type: 'button', onClick: a.onPress, 'aria-label': `${a.label}|${a.detail ?? ''}` }, a.label))) : null),
}));
vi.mock('../../components/AlertBanner', () => ({ AlertBanner: ({ lead }) => React.createElement('div', { role: 'alert' }, lead) }));
vi.mock('../../components/Busy', () => ({ Busy: () => null }));
vi.mock('../../components/Button', () => ({
  Button: ({ title, onPress, disabled }) => React.createElement('button', { type: 'button', onClick: onPress, disabled }, title),
}));
vi.mock('../../components/Icon', () => ({ Icon: () => null }));
vi.mock('../../components/LoadFailed', () => ({ LoadFailed: () => React.createElement('div', {}, 'load failed') }));
vi.mock('../../components/RichText', () => ({ RichText: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../../components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../../components/TypedConfirm', () => ({
  Bold: ({ children }) => React.createElement('b', {}, children),
  TypedConfirm: ({ open, expected, onConfirm, confirmLabel }) => (open ? React.createElement('button', { type: 'button', 'data-expected': expected, onClick: onConfirm }, confirmLabel) : null),
}));
vi.mock('../../hooks/useAttention', () => ({ useAttention: () => ({ att: null, refresh: vi.fn() }) }));
vi.mock('../../hooks/useBusyVisible', () => ({ useBusyVisible: () => false }));
vi.mock('../../hooks/useDaemonData', () => ({ useScheduleList: () => ({ data: { jobs: h.jobs }, loading: false, error: null, refresh: h.refresh }) }));
vi.mock('../../hooks/useEvents', () => ({ useEventEffect: (_events, fn) => { h.handlers.push(fn); } }));
vi.mock('../../hooks/useOutputs', () => ({ useOutputs: () => ({ rows: h.outputs }) }));
vi.mock('../../hooks/usePullRefresh', () => ({ usePullRefresh: () => ({ refreshing: false, onRefresh: vi.fn() }) }));
vi.mock('../../hooks/useActivity', async (importOriginal) => ({ ...(await importOriginal()), useActivity: () => ({ activity: h.activity }) }));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call }) }));
vi.mock('../../lib/clipboard', () => ({ copyText: async (text) => { h.copied.push(text); return true; } }));
vi.mock('../profile/PanelHeader', () => ({ PanelHeader: ({ right }) => React.createElement('header', {}, right) }));
vi.mock('../profile/StatusWord', () => ({ StatusWord: ({ word, danger }) => React.createElement('i', { 'data-status': word, 'data-danger': String(!!danger) }) }));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', danger: '#c14545', dangerText: '#b73737', line: '#ddd', line2: '#ccc', hover: '#eee', selected: '#eee' },
      fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

import { JobDetail, confirmWord, statusOf } from './JobDetail';

const NOW = Date.now();
const JOB = {
  id: '7be40d19',
  title: 'Daily review digest',
  description: 'Summarises new guest reviews.',
  kind: 'cron',
  expression: '30 7 * * *',
  paused: false,
  notify: false,
  last_run_status: 'error',
  last_run_at: new Date(NOW - 3600_000).toISOString(),
  last_run_message: 'timed out',
  next_fire: new Date(NOW + 20 * 3600_000).toISOString(),
  run_timeout: 1200,
  prompt: 'Summarise.',
};

function mount(props = {}) {
  return render(<JobDetail profile="scout" jobId={JOB.id} onBack={vi.fn()} onGone={props.onGone ?? vi.fn()} {...props} />);
}

function emit(event, data) {
  act(() => { h.handlers.forEach((fn) => fn({ event, data: { profile: 'scout', ...data } })); });
}

beforeEach(() => {
  h.push.mockClear();
  h.toast.mockClear();
  h.refresh.mockClear();
  h.jobs = [JOB];
  h.activity = { running: [] };
  h.outputs = [];
  h.copied = [];
  h.call = vi.fn(async () => ({ ok: true }));
});
afterEach(() => {
  cleanup();
  h.handlers.length = 0;
  vi.useRealTimers();
});

describe('job page status', () => {
  it('says failed for a failed job, paused for a paused one and active otherwise', () => {
    expect(statusOf(JOB, false)).toEqual({ word: 'failed', on: false, danger: true });
    expect(statusOf({ ...JOB, paused: true }, false).word).toBe('paused');
    expect(statusOf({ ...JOB, last_run_status: 'ok' }, false).word).toBe('active');
    expect(statusOf(JOB, true).word).toBe('running');
  });

  it('draws the word and leaves the raw id off the page', () => {
    mount();
    expect(document.querySelector('[data-status]').getAttribute('data-status')).toBe('failed');
    expect(screen.queryByText(JOB.id)).toBeNull();
  });
});

describe('running', () => {
  it('turns Run now into Running with the elapsed time while an activity row carries the job', () => {
    h.activity = { running: [{ kind: 'turn', profile: 'scout', source: 'schedule', job_id: JOB.id, started_at: NOW / 1000 - 42 }] };
    mount();
    expect(screen.getByText(/^Running · 0:4\d$/).disabled).toBe(true);
    expect(document.querySelector('[data-status]').getAttribute('data-status')).toBe('running');
    expect(screen.getByText('Pause').disabled).toBe(true);
  });

  it('keeps the failure banner while the job runs again so the buttons do not move', async () => {
    mount();
    expect(screen.getByRole('alert')).toBeTruthy();
    fireEvent.click(screen.getByText('Run now'));
    await screen.findByText('Running · 0:00');
    expect(screen.getByRole('alert')).toBeTruthy();
  });

  it('fires the job, shows Running at once and ends it with the event, toasting View for the output', async () => {
    mount();
    fireEvent.click(screen.getByText('Run now'));
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.schedule.fire', { profile: 'scout', id: JOB.id }));
    await screen.findByText('Running · 0:00');
    emit('schedule.done', { job_id: JOB.id, output_id: 'o9' });
    await screen.findByText('Run now');
    expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ message: 'Daily review digest finished', kind: 'success', action: 'View' }));
    h.toast.mock.calls[0][0].onAction();
    expect(h.push).toHaveBeenCalledWith('/outputs/scout/o9');
  });

  it('ends the running state on a failure without a second toast, and ignores another job', async () => {
    mount();
    fireEvent.click(screen.getByText('Run now'));
    await screen.findByText('Running · 0:00');
    emit('schedule.done', { job_id: 'someone-else' });
    expect(screen.queryByText('Running · 0:00')).toBeTruthy();
    emit('schedule.failed', { job_id: JOB.id });
    await screen.findByText('Run now');
    expect(h.toast).not.toHaveBeenCalled();
  });

  it('does not toast a run it never showed as running', () => {
    mount();
    emit('schedule.done', { job_id: JOB.id });
    expect(h.toast).not.toHaveBeenCalled();
  });

  it('fires the job once when Run now is tapped twice before the screen has redrawn', async () => {
    mount();
    const button = screen.getByText('Run now');
    act(() => { fireEvent.click(button); fireEvent.click(button); });
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.schedule.fire', { profile: 'scout', id: JOB.id }));
    expect(h.call.mock.calls.filter(([method]) => method === 'host.schedule.fire')).toHaveLength(1);
  });

  it('drops the running state when firing fails', async () => {
    h.call = vi.fn(async () => { throw new Error('daemon unreachable'); });
    mount();
    fireEvent.click(screen.getByText('Run now'));
    await waitFor(() => expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ kind: 'danger' })));
    expect(screen.getByText('Run now').disabled).toBe(false);
  });
});

describe('one-shot jobs', () => {
  it('describes the time in words and leaves the raw ISO stamp off the page', () => {
    const runAt = new Date(NOW + 14 * 3600_000).toISOString();
    h.jobs = [{ ...JOB, kind: 'once', expression: undefined, run_at: runAt, last_run_status: 'ok' }];
    mount();
    expect(screen.queryByText(runAt)).toBeNull();
    expect(screen.getAllByText(/^once, /).length).toBeGreaterThan(0);
  });
});

describe('changing a job', () => {
  it('opens the profile chat with a draft naming the job', () => {
    mount();
    fireEvent.click(screen.getByLabelText('Ask the agent to change this'));
    expect(h.push).toHaveBeenCalledWith(`/chat/scout?draft=${encodeURIComponent('Change the schedule “Daily review digest” (job 7be40d19): ')}`);
  });
});

describe('more', () => {
  it('offers the id, and the last output only when one exists', () => {
    mount();
    fireEvent.click(screen.getByLabelText('More'));
    expect(screen.getByLabelText('Copy job id|7be40d19')).toBeTruthy();
    expect(screen.queryByLabelText(/^Last output/)).toBeNull();
    cleanup();
    h.outputs = [{ id: 'o1', job_id: 'other', profile: 'scout' }, { id: 'o2', job_id: JOB.id, profile: 'scout' }];
    mount();
    fireEvent.click(screen.getByLabelText('More'));
    fireEvent.click(screen.getByLabelText('Last output|opens the notification'));
    expect(h.push).toHaveBeenCalledWith('/outputs/scout/o2');
  });

  it('copies the id', async () => {
    mount();
    fireEvent.click(screen.getByLabelText('More'));
    fireEvent.click(screen.getByLabelText('Copy job id|7be40d19'));
    await waitFor(() => expect(h.copied).toEqual([JOB.id]));
    expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ message: 'Copied' }));
  });

  it('deletes only after the typed confirm, naming the title to type', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const onGone = vi.fn();
    mount({ onGone });
    fireEvent.click(screen.getByLabelText('More'));
    fireEvent.click(screen.getByLabelText('Delete job…|'));
    expect(h.call).not.toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(400); });
    const confirm = screen.getByText('Delete job');
    expect(confirm.getAttribute('data-expected')).toBe('Daily review digest');
    fireEvent.click(confirm);
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.schedule.remove', { profile: 'scout', id: JOB.id }));
    await waitFor(() => expect(onGone).toHaveBeenCalled());
  });

  it('asks for the id when the title is too long to type', () => {
    expect(confirmWord({ id: 'abc12345', title: 'x'.repeat(40) })).toBe('abc12345');
    expect(confirmWord({ id: 'abc12345', title: 'Weekly labs' })).toBe('Weekly labs');
  });
});
