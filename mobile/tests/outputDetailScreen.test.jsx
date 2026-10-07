import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  params: {},
  row: null,
  runJob: vi.fn(async () => ({})),
  push: vi.fn(),
  toast: vi.fn(),
  activeId: 'casa',
  role: 'admin',
  connections: [{ id: 'casa', name: 'casa' }],
  setParams: vi.fn(),
  replace: vi.fn(),
  back: vi.fn(),
  setActive: vi.fn(async () => {}),
  markRead: vi.fn(async () => {}),
  markUnread: vi.fn(async () => ({})),
  remove: vi.fn(),
  undoRemove: vi.fn(),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityRole, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, numberOfLines, selectable, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, style, accessibilityRole, accessibilityState, accessibilityLabel, hitSlop, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'aria-expanded': accessibilityState?.expanded }, typeof children === 'function' ? children({ pressed: false }) : children);
  return {
    View,
    Text,
    Pressable,
    ScrollView: ({ children }) => React.createElement('div', {}, children),
  };
});
vi.mock('expo-clipboard', () => ({ setStringAsync: vi.fn() }));
vi.mock('expo-router', () => ({
  useLocalSearchParams: () => h.params,
  useRouter: () => ({ push: h.push, back: h.back, setParams: h.setParams, replace: h.replace }),
}));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/components/ActionSheet', () => ({
  ActionSheet: ({ open, actions }) => (open
    ? React.createElement('div', { 'data-sheet': '' }, actions.map((a) => React.createElement('button', { key: a.id, type: 'button', onClick: a.onPress }, a.label)))
    : null),
}));
vi.mock('../src/theme/ThemeContext', async () => {
  const tokens = await import('../src/theme/tokens');
  return {
    useTheme: () => ({
      mode: 'light',
      colors: { bg: '#f0f0f0', bgPane: '#fff', bgSide: '#f6f6f6', ink: '#000', ink2: '#333', ink3: '#666', line: '#ddd', hover: '#eee', selected: '#ddd', danger: '#e00', dangerText: '#b00', warningText: '#a60' },
      fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
      fontSizes: tokens.fontSizes,
    }),
  };
});
vi.mock('../src/components/Fold', () => ({ Fold: () => null }));
vi.mock('../src/components/Icon', () => ({ Icon: ({ name, color }) => React.createElement('i', { 'data-icon': name, 'data-color': color }) }));
vi.mock('../src/components/Button', () => ({
  Button: ({ title, onPress, loading }) => React.createElement('button', { type: 'button', onClick: onPress, disabled: loading }, title),
}));
vi.mock('../src/components/ScreenHeader', () => ({
  ScreenHeader: ({ title, right }) => React.createElement('header', {}, React.createElement('h1', {}, title), right),
}));
vi.mock('../src/components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => h.back }));
vi.mock('../src/hooks/useDaemonData', () => ({ useProfileSummaries: () => ({ data: { profiles: [] } }) }));
vi.mock('../src/hooks/useOutputs', () => ({
  useOutput: () => ({ row: h.row, loading: false, error: null, markRead: h.markRead, markUnread: h.markUnread, runJob: h.runJob }),
  useNotificationActions: () => ({ remove: h.remove, undoRemove: h.undoRemove }),
  unreadMissingKey: (connectionId, activeId) => connectionId || activeId || 'active',
}));
vi.mock('../src/features/aln/deeplink', () => ({ isForeignConnection: (activeId, connectionId) => !!connectionId && !!activeId && connectionId !== activeId }));
vi.mock('../src/hooks/useActiveRole', () => ({ useIsAdmin: () => h.role === 'admin' }));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({ activeId: h.activeId, connections: h.connections, setActive: h.setActive }),
}));

import OutputDetailScreen from '../app/outputs/[profile]/[id].jsx';
import { _resetNotificationStoreForTests, notificationState, setTrail } from '../src/lib/notificationStore';

const FAILED = {
  id: 'f1', profile: 'abby', type: 'error', status: 'read', created_at: 1_700_000_000, title: 'Daily mail digest failed', job_id: 'j-mail',
  body: '**Reason:** The mail account refused the saved token.\n**Exit:** 1\n\n```text\nTraceback (most recent call last)\n```',
};

beforeEach(() => {
  _resetNotificationStoreForTests();
  for (const fn of [h.setParams, h.replace, h.back, h.setActive, h.markRead, h.markUnread, h.remove, h.undoRemove, h.toast]) fn.mockClear();
  h.connections = [{ id: 'casa', name: 'casa' }];
  h.params = { profile: 'abby', id: 'f1' };
  h.row = FAILED;
  h.runJob.mockClear();
  h.push.mockClear();
  h.activeId = 'casa';
  h.role = 'admin';
});

describe('notification page, failed run', () => {
  it('draws the error card: red only on the mark and the word failed, facts, the trace folded under Details', () => {
    const { container } = render(<OutputDetailScreen />);
    expect(container.querySelector('[data-icon="triangle-alert"]').getAttribute('data-color')).toBe('#e00');
    expect(screen.getByText('failed', { normalizer: (t) => t.trim() })).toBeTruthy();
    expect(screen.getByText('REASON')).toBeTruthy();
    expect(screen.getByText('EXIT')).toBeTruthy();
    expect(screen.queryByText('ERROR')).toBeNull();
    expect(screen.queryByText(/Traceback/)).toBeNull();
    fireEvent.click(screen.getByLabelText('Details'));
    expect(screen.getByText(/Traceback/)).toBeTruthy();
  });

  it('runs the job again and opens it on the schedule screen', async () => {
    render(<OutputDetailScreen />);
    await act(async () => { fireEvent.click(screen.getByText('Run again')); });
    expect(h.runJob).toHaveBeenCalledWith('j-mail');
    fireEvent.click(screen.getByText('Open job'));
    expect(h.push).toHaveBeenCalledWith({ pathname: '/profile/[id]/schedule', params: { id: 'abby', job: 'j-mail' } });
  });

  it('runs the job once however often Run again is tapped while it starts', async () => {
    let release;
    h.runJob.mockImplementationOnce(() => new Promise((resolve) => { release = resolve; }));
    render(<OutputDetailScreen />);
    await act(async () => { fireEvent.click(screen.getByText('Run again')); fireEvent.click(screen.getByText('Run again')); });
    expect(h.runJob).toHaveBeenCalledTimes(1);
    await act(async () => { release({}); });
  });

  it('offers no job actions for a failure from a connection that is not active', () => {
    h.params = { profile: 'abby', id: 'f1', connectionId: 'mirai' };
    render(<OutputDetailScreen />);
    expect(screen.queryByText('Run again')).toBeNull();
    expect(screen.queryByText('Open job')).toBeNull();
  });

  it('offers no job actions on a member device, which cannot run or open jobs', () => {
    h.role = 'member';
    render(<OutputDetailScreen />);
    expect(screen.queryByText('Run again')).toBeNull();
    expect(screen.queryByText('Open job')).toBeNull();
  });

  it('offers no job actions when the failure names no job', () => {
    h.row = { ...FAILED, job_id: undefined };
    render(<OutputDetailScreen />);
    expect(screen.queryByText('Run again')).toBeNull();
    expect(screen.queryByText('Open job')).toBeNull();
  });
});

describe('notification page, digest', () => {
  it('draws each entry as name, address in mono and the text under it', () => {
    h.row = { ...FAILED, type: 'info', title: 'Daily mail digest', body: '- **Ana Ruiz** <ana@example.com> — Can we move Friday?\n- **Bob** — Invoice' };
    render(<OutputDetailScreen />);
    expect(screen.getByText('Ana Ruiz')).toBeTruthy();
    expect(screen.getByText('ana@example.com')).toBeTruthy();
    expect(screen.getByText('Can we move Friday?')).toBeTruthy();
    expect(screen.queryByText(/<ana@example.com>/)).toBeNull();
  });
});

const DIGEST = { id: 'd1', profile: 'abby', type: 'info', status: 'read', created_at: 1_700_000_000, title: 'Daily mail digest', job_id: 'j-mail', body: '14 new emails since yesterday.', session_id: 's-9' };
const entry = (id, connectionId = 'casa', profile = 'abby') => ({ key: `${connectionId}:${profile}:${id}`, profile, id, connectionId, pinned: false, unread: false });

describe('notification page, bottom bar', () => {
  beforeEach(() => {
    h.row = DIGEST;
    h.params = { profile: 'abby', id: 'd1', connectionId: 'casa' };
  });

  it('replies in a new session with the notification quoted in the composer', () => {
    render(<OutputDetailScreen />);
    fireEvent.click(screen.getByText('Reply'));
    const [{ pathname, params }] = h.push.mock.calls.at(-1);
    expect(pathname).toBe('/chat/[id]');
    expect(params.id).toBe('abby');
    expect(params.connectionId).toBe('casa');
    expect(params.fresh).toBeTruthy();
    expect(params.draft).toBe('> **Daily mail digest**\n>\n> 14 new emails since yesterday.\n\n');
  });

  it('keeps Open job at the thumb for an admin on the active connection', () => {
    render(<OutputDetailScreen />);
    fireEvent.click(screen.getByText('Open job'));
    expect(h.push).toHaveBeenCalledWith({ pathname: '/profile/[id]/schedule', params: { id: 'abby', job: 'j-mail' } });
  });

  it.each([
    ['a member device', () => { h.role = 'member'; }],
    ['another connection', () => { h.params = { ...h.params, connectionId: 'mirai' }; }],
    ['a notification with no job', () => { h.row = { ...DIGEST, job_id: undefined }; }],
  ])('offers no Open job on %s', (_label, arrange) => {
    arrange();
    render(<OutputDetailScreen />);
    expect(screen.getByText('Reply')).toBeTruthy();
    expect(screen.queryByText('Open job')).toBeNull();
  });

  it('copies and opens the chat from the overflow', async () => {
    render(<OutputDetailScreen />);
    fireEvent.click(screen.getByLabelText('More'));
    expect(screen.getByText('Copy')).toBeTruthy();
    fireEvent.click(screen.getByText('Open chat'));
    expect(h.push).toHaveBeenCalledWith({ pathname: '/chat/[id]', params: { id: 'abby', sid: 's-9', connectionId: 'casa' } });
  });

  it('leaves Open chat out of the overflow when the row knows no session', () => {
    h.row = { ...DIGEST, session_id: undefined };
    render(<OutputDetailScreen />);
    fireEvent.click(screen.getByLabelText('More'));
    expect(screen.queryByText('Open chat')).toBeNull();
  });
});

describe('notification page, read state', () => {
  beforeEach(() => {
    h.params = { profile: 'abby', id: 'd1', connectionId: 'casa' };
  });

  it('marks an unread notification read once when it opens', () => {
    h.row = { ...DIGEST, status: 'unread' };
    const { rerender } = render(<OutputDetailScreen />);
    h.row = { ...DIGEST, status: 'unread' };
    rerender(<OutputDetailScreen />);
    expect(h.markRead).toHaveBeenCalledTimes(1);
    expect(screen.queryByLabelText('Mark unread')).toBeNull();
  });

  it('marks it unread on the connection it came from', async () => {
    h.row = DIGEST;
    render(<OutputDetailScreen />);
    await act(async () => { fireEvent.click(screen.getByLabelText('Mark unread')); });
    expect(h.markUnread).toHaveBeenCalledTimes(1);
    expect(h.markRead).not.toHaveBeenCalled();
  });

  it('hides Mark unread once the daemon answers method-not-found', async () => {
    h.row = DIGEST;
    h.markUnread.mockRejectedValueOnce(Object.assign(new Error('unknown method: host.outputs.mark_unread'), { code: -32601 }));
    render(<OutputDetailScreen />);
    await act(async () => { fireEvent.click(screen.getByLabelText('Mark unread')); });
    expect(screen.queryByLabelText('Mark unread')).toBeNull();
    expect(notificationState().unreadMissing.has('casa')).toBe(true);
    expect(h.toast).not.toHaveBeenCalledWith(expect.objectContaining({ kind: 'danger' }));
  });
});

describe('notification page, moving between notifications', () => {
  beforeEach(() => {
    h.row = DIGEST;
    setTrail([entry('a'), entry('d1'), entry('z', 'mirai', 'sentinel')]);
    h.params = { profile: 'abby', id: 'd1', connectionId: 'casa' };
  });

  it('says where it is in the list it came from and steps up and down', async () => {
    render(<OutputDetailScreen />);
    expect(screen.getByText('2 of 3')).toBeTruthy();
    await act(async () => { fireEvent.click(screen.getByLabelText('Previous notification')); });
    expect(h.setParams).toHaveBeenLastCalledWith({ profile: 'abby', id: 'a', connectionId: 'casa' });
    await act(async () => { fireEvent.click(screen.getByLabelText('Next notification')); });
    expect(h.setActive).toHaveBeenCalledWith('mirai');
    expect(h.setParams).toHaveBeenLastCalledWith({ profile: 'sentinel', id: 'z', connectionId: 'mirai' });
    expect(notificationState().frozen.key).toBe('mirai:sentinel:z');
  });

  it('draws no counter or arrows on a deep link the list did not order', () => {
    h.params = { profile: 'abby', id: 'other' };
    render(<OutputDetailScreen />);
    expect(screen.queryByText(/ of /)).toBeNull();
    expect(screen.queryByLabelText('Previous notification')).toBeNull();
    expect(screen.queryByLabelText('Next notification')).toBeNull();
  });

  it('deletes with an undo, then moves to the next notification', async () => {
    render(<OutputDetailScreen />);
    await act(async () => { fireEvent.click(screen.getByLabelText('Delete')); });
    expect(h.remove).toHaveBeenCalledWith({ profile: 'abby', id: 'd1', connectionId: 'casa' }, expect.objectContaining({ onError: expect.any(Function) }));
    const shown = h.toast.mock.calls.at(-1)[0];
    expect(shown.action).toBe('Undo');
    shown.onAction();
    expect(h.undoRemove).toHaveBeenCalledWith({ profile: 'abby', id: 'd1', connectionId: 'casa' });
    expect(h.setParams).toHaveBeenLastCalledWith({ profile: 'sentinel', id: 'z', connectionId: 'mirai' });
  });

  it('goes back after deleting the last notification', async () => {
    h.params = { profile: 'sentinel', id: 'z', connectionId: 'mirai' };
    h.activeId = 'mirai';
    render(<OutputDetailScreen />);
    await act(async () => { fireEvent.click(screen.getByLabelText('Delete')); });
    expect(h.back).toHaveBeenCalled();
    expect(h.setParams).not.toHaveBeenCalled();
  });
});
