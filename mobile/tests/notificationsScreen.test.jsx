import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  rows: [],
  push: vi.fn(),
  toast: vi.fn(),
  refresh: vi.fn(async () => {}),
  rpc: vi.fn(async () => ({ ok: true })),
  setActive: vi.fn(async () => {}),
  roles: new Map([['casa', 'admin'], ['mirai', 'admin']]),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityRole, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, numberOfLines, accessibilityRole, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, accessibilityLabel, accessibilityState, accessibilityActions, onAccessibilityAction }) =>
    React.createElement(
      'div',
      { role: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'aria-selected': accessibilityState?.selected },
      typeof children === 'function' ? children({ pressed: false }) : children,
      ...(accessibilityActions ?? []).map((a) => React.createElement('span', {
        key: a.name,
        'data-a11y-action': a.label,
        'data-for': accessibilityLabel,
        onClick: (e) => { e.stopPropagation(); onAccessibilityAction({ nativeEvent: { actionName: a.name } }); },
      })),
    );
  const FlatList = ({ data, renderItem, keyExtractor, ListHeaderComponent, ListEmptyComponent }) =>
    React.createElement(
      'div',
      { 'data-list': '' },
      ListHeaderComponent,
      data.length
        ? data.map((item) => React.createElement(React.Fragment, { key: keyExtractor(item) }, renderItem({ item })))
        : ListEmptyComponent,
    );
  return {
    View,
    Text,
    Pressable,
    FlatList,
    ScrollView: ({ children }) => React.createElement('div', {}, children),
    RefreshControl: () => null,
    AccessibilityInfo: { isReduceMotionEnabled: async () => false, addEventListener: () => ({ remove: () => {} }) },
  };
});
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, back: vi.fn() }),
  useFocusEffect: () => {},
}));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', async () => {
  const tokens = await import('../src/theme/tokens');
  return {
    useTheme: () => ({
      mode: 'light',
      colors: { bg: '#f0f0f0', bgPane: '#ffffff', ink: '#141414', ink2: '#454545', ink3: '#6b6b6b', line: '#eeeeee', hover: '#f4f4f4', selected: '#eaeaea', dangerText: '#b73737', warningText: '#b3470e' },
      fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
      fontSizes: tokens.fontSizes,
    }),
  };
});
vi.mock('../src/components/Fold', () => ({ Fold: () => null }));
vi.mock('../src/components/Button', () => ({
  Button: ({ title, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, title),
}));
vi.mock('../src/components/ScreenHeader', () => ({
  ScreenHeader: ({ title, subtitle, right }) => React.createElement('header', {}, React.createElement('h1', {}, title), React.createElement('span', { 'data-subtitle': '' }, subtitle), right),
}));
vi.mock('../src/components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => vi.fn() }));
vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/lib/rpc', () => ({ call: h.rpc }));
vi.mock('../src/hooks/useUnifiedOutputs', async (importOriginal) => ({
  ...(await importOriginal()),
  useUnifiedOutputs: () => ({ rows: h.rows, loading: false, refresh: h.refresh, hasAdmin: true, unreachable: false, unreachableCount: 0 }),
}));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({
    endpoint: { id: 'casa' },
    activeId: 'casa',
    connections: [{ id: 'casa', name: 'casa', url: 'http://casa' }, { id: 'mirai', name: 'mirai', url: 'http://mirai' }],
    roleState: h.roles,
    setActive: h.setActive,
    call: vi.fn(),
  }),
}));

import OutputsScreen from '../app/outputs.jsx';
import { _resetNotificationStoreForTests, notificationState } from '../src/lib/notificationStore';

const NOW = Date.now() / 1000;
const START_OF_TODAY = new Date(new Date().setHours(0, 0, 0, 0)).getTime() / 1000;
const row = (id, profile, connectionId, extra = {}) => ({
  id, profile, connectionId, connectionName: connectionId, fold: 'plane', accent: '#df4b9d', created_at: Math.max(NOW - 60, START_OF_TODAY + 1), type: 'info', status: 'read', title: `${profile} ${id}`, body: 'Body line.', ...extra,
});
const ROWS = () => [
  row('e1', 'abby', 'casa', { type: 'error', status: 'unread', title: 'Mail digest failed' }),
  row('i1', 'abby', 'casa', { status: 'unread', title: 'Daily mail digest' }),
  row('w1', 'sentinel', 'mirai', { type: 'warning', title: 'PR waiting' }),
  row('y1', 'curator', 'mirai', { created_at: START_OF_TODAY - 3600 * 12, title: 'Knowledge pass' }),
];

const rowTitles = () => Array.from(document.querySelectorAll('[data-swipeable] > [role="button"]')).map((el) => el.getAttribute('aria-label'));
const a11yAction = (title, label) => {
  const host = Array.from(document.querySelectorAll('[data-swipeable] > [role="button"]')).find((el) => (el.getAttribute('aria-label') ?? '').includes(title));
  return host.querySelector(`[data-a11y-action="${label}"]`);
};

beforeEach(() => {
  _resetNotificationStoreForTests();
  h.rows = ROWS();
  for (const fn of [h.push, h.toast, h.refresh, h.setActive]) fn.mockClear();
  h.rpc.mockReset().mockResolvedValue({ ok: true });
});

describe('notifications list, triage', () => {
  it('pins unread errors and warnings above the day groups', () => {
    render(<OutputsScreen />);
    const text = document.body.textContent;
    expect(text.indexOf('Needs you · 1')).toBeLessThan(text.indexOf('Today'));
    expect(text.indexOf('Today')).toBeLessThan(text.indexOf('Yesterday'));
    expect(rowTitles()[0]).toContain('Mail digest failed');
    expect(rowTitles()[0]).toMatch(/^Unread, error, @abby on casa/);
  });

  it('counts each filter and narrows to it', () => {
    render(<OutputsScreen />);
    expect(screen.getByLabelText('All, 4')).toBeTruthy();
    expect(screen.getByLabelText('Needs you, 1')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Unread, 2'));
    expect(rowTitles()).toHaveLength(2);
    expect(document.body.textContent).not.toContain('Needs you · 1');
    fireEvent.click(screen.getByLabelText('Needs you, 1'));
    expect(rowTitles()).toEqual([expect.stringContaining('Mail digest failed')]);
  });

  it('draws no per-profile tags or counts above the list', () => {
    render(<OutputsScreen />);
    expect(screen.queryByLabelText(/^@sentinel/)).toBeNull();
    expect(screen.queryByLabelText(/^@abby/)).toBeNull();
  });

  it('marks unread with an ink dot and severity with a word', () => {
    render(<OutputsScreen />);
    expect(screen.getByText('ERROR')).toBeTruthy();
    expect(screen.getByText('WARNING')).toBeTruthy();
    expect(screen.queryByText('INFO')).toBeNull();
  });

  it('keeps the row being read in Unread after it turns read, until the reader moves on', async () => {
    const { rerender } = render(<OutputsScreen />);
    fireEvent.click(screen.getByLabelText('Unread, 2'));
    await act(async () => { fireEvent.click(screen.getByLabelText(/Daily mail digest/)); });
    expect(h.push).toHaveBeenCalledWith({ pathname: '/outputs/[profile]/[id]', params: { profile: 'abby', id: 'i1', connectionId: 'casa' } });
    expect(notificationState().trail.map((e) => e.id)).toEqual(['e1', 'i1']);
    h.rows = ROWS().map((r) => (r.id === 'i1' ? { ...r, status: 'read' } : r));
    rerender(<OutputsScreen />);
    expect(rowTitles()).toHaveLength(2);
    fireEvent.click(screen.getByLabelText('All, 4'));
    fireEvent.click(screen.getByLabelText('Unread, 1'));
    expect(rowTitles()).toHaveLength(1);
  });
});

describe('notifications list, row actions', () => {
  it('swipes to Unread and Delete, both reachable without the gesture', () => {
    render(<OutputsScreen />);
    const swipe = document.querySelector('[data-swipe-actions]');
    expect(within(swipe).getByLabelText('Read')).toBeTruthy();
    expect(within(swipe).getByLabelText('Delete')).toBeTruthy();
    expect(a11yAction('PR waiting', 'Mark unread')).toBeTruthy();
    expect(a11yAction('PR waiting', 'Delete')).toBeTruthy();
    expect(a11yAction('Daily mail digest', 'Mark read')).toBeTruthy();
  });

  it('marks a row unread on the daemon that filed it', async () => {
    render(<OutputsScreen />);
    await act(async () => { fireEvent.click(a11yAction('PR waiting', 'Mark unread')); });
    expect(h.rpc).toHaveBeenCalledWith(expect.objectContaining({ id: 'mirai' }), 'host.outputs.mark_unread', { profile: 'sentinel', id: 'w1' });
    expect(rowTitles().find((t) => t.includes('PR waiting'))).toMatch(/^Unread, warning/);
    expect(document.body.textContent).toContain('Needs you · 2');
  });

  it('marks an unread row read from the list', async () => {
    render(<OutputsScreen />);
    await act(async () => { fireEvent.click(a11yAction('Daily mail digest', 'Mark read')); });
    expect(h.rpc).toHaveBeenCalledWith(expect.objectContaining({ id: 'casa' }), 'host.outputs.mark_read', { profile: 'abby', id: 'i1' });
  });

  it('shows a row unread again when marking it read fails', async () => {
    h.rpc.mockImplementation(async (_conn, method) => {
      if (method === 'host.outputs.mark_read') throw new Error('offline');
      return { ok: true };
    });
    render(<OutputsScreen />);
    await act(async () => { fireEvent.click(a11yAction('Daily mail digest', 'Mark read')); });
    expect(rowTitles().find((t) => t.includes('Daily mail digest'))).toMatch(/^Unread/);
  });

  it('says so when a delete fails, and treats a row already gone as deleted', async () => {
    vi.useFakeTimers();
    try {
      h.rpc.mockImplementation(async (_conn, method, params) => {
        if (method === 'host.outputs.delete' && params.id === 'y1') throw new Error('forbidden');
        if (method === 'host.outputs.delete') throw new Error('alp -32004: not-found');
        return { ok: true };
      });
      render(<OutputsScreen />);
      act(() => { fireEvent.click(a11yAction('Knowledge pass', 'Delete')); });
      act(() => { fireEvent.click(a11yAction('PR waiting', 'Delete')); });
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      expect(rowTitles().some((t) => t.includes('Knowledge pass'))).toBe(true);
      expect(rowTitles().some((t) => t.includes('PR waiting'))).toBe(false);
      expect(h.toast.mock.calls.some(([arg]) => /Delete failed: forbidden/.test(arg.message))).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it('stops offering Mark unread on a daemon that lacks the verb', async () => {
    h.rpc.mockImplementation(async (_conn, method) => {
      if (method === 'host.outputs.mark_unread') throw Object.assign(new Error('unknown method'), { code: -32601 });
      return { ok: true };
    });
    render(<OutputsScreen />);
    await act(async () => { fireEvent.click(a11yAction('PR waiting', 'Mark unread')); });
    expect(a11yAction('PR waiting', 'Mark unread')).toBeNull();
    expect(a11yAction('Knowledge pass', 'Mark unread')).toBeNull();
    expect(a11yAction('PR waiting', 'Delete')).toBeTruthy();
    expect(rowTitles().find((t) => t.includes('PR waiting'))).not.toMatch(/^Unread/);
  });

  it('deletes after the undo window and brings the row back on Undo', async () => {
    vi.useFakeTimers();
    try {
      render(<OutputsScreen />);
      act(() => { fireEvent.click(a11yAction('Knowledge pass', 'Delete')); });
      expect(rowTitles().some((t) => t.includes('Knowledge pass'))).toBe(false);
      const undo = h.toast.mock.calls.at(-1)[0];
      expect(undo.action).toBe('Undo');
      act(() => { undo.onAction(); });
      expect(rowTitles().some((t) => t.includes('Knowledge pass'))).toBe(true);
      await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
      expect(h.rpc).not.toHaveBeenCalledWith(expect.anything(), 'host.outputs.delete', expect.anything());

      act(() => { fireEvent.click(a11yAction('Knowledge pass', 'Delete')); });
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      expect(h.rpc).toHaveBeenCalledWith(expect.objectContaining({ id: 'mirai' }), 'host.outputs.delete', { profile: 'curator', id: 'y1' });
      expect(rowTitles().some((t) => t.includes('Knowledge pass'))).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('notifications list, access', () => {
  it('stays unavailable on a member-only device, as before', () => {
    const roles = h.roles;
    h.roles = new Map([['casa', 'member'], ['mirai', 'member']]);
    h.rows = [];
    try {
      render(<OutputsScreen />);
      expect(screen.getByText('Notifications unavailable')).toBeTruthy();
      expect(screen.queryByLabelText('All, 0')).toBeNull();
    } finally {
      h.roles = roles;
    }
  });
});

describe('notifications list, leaving', () => {
  it('forgets the reading order and the kept row once the list goes away', async () => {
    const { unmount } = render(<OutputsScreen />);
    await act(async () => { fireEvent.click(screen.getByLabelText(/Daily mail digest/)); });
    expect(notificationState().trail).not.toBeNull();
    expect(notificationState().frozen).not.toBeNull();
    unmount();
    expect(notificationState().trail).toBeNull();
    expect(notificationState().frozen).toBeNull();
  });
});
