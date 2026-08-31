import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  store: new Map(),
  subscription: { kinds: [], fn: null },
  appStateListeners: [],
  currentState: 'active',
  endpoint: null,
  connections: [],
  fireMock: vi.fn(async () => true),
  permMock: vi.fn(async () => 'granted'),
  requestPermMock: vi.fn(async () => 'granted'),
  pollMock: vi.fn(async () => ({ groups: 1, notifications: 0 })),
  primer: { open: false, onEnable: null, onDecline: null },
}));

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(async (k) => (h.store.has(k) ? h.store.get(k) : null)),
  setItemAsync: vi.fn(async (k, v) => { h.store.set(k, v); }),
  deleteItemAsync: vi.fn(async (k) => { h.store.delete(k); }),
}));

vi.mock('react-native', () => ({
  AppState: {
    addEventListener: (_type, fn) => {
      h.appStateListeners.push(fn);
      return { remove: () => { h.appStateListeners = h.appStateListeners.filter((l) => l !== fn); } };
    },
    get currentState() { return h.currentState; },
  },
}));

vi.mock('../../hooks/useEvents', () => ({
  useEventEffect: (kinds, fn) => {
    h.subscription.kinds = kinds;
    h.subscription.fn = fn;
  },
}));

vi.mock('../../lib/EndpointContext', () => ({
  useEndpoint: () => ({ endpoint: h.endpoint, connections: h.connections }),
}));

// fireForEvent is consumed by the real ./deliver, which this suite deliberately does NOT mock.
vi.mock('./notify', () => ({
  fireForEvent: h.fireMock,
  getPermissionStatus: h.permMock,
  requestPermission: h.requestPermMock,
}));

vi.mock('./NotificationPrimer', () => ({
  NotificationPrimer: ({ open, onEnable, onDecline }) => {
    h.primer = { open, onEnable, onDecline };
    return null;
  },
}));

vi.mock('./backgroundTask', () => ({
  runPollOnce: h.pollMock,
}));

import { NotificationBridge } from './NotificationBridge';
import { NOTIFIABLE_KINDS } from './kinds';
import { loadState, saveState } from './state';

const CONN = { id: 'c1', name: 'home', deviceId: 'mac', token: 't' };

// Mirrors useEventEffect's own filter so a non-notifiable kind can never reach the bridge.
function emit(event) {
  const kinds = Array.isArray(h.subscription.kinds) ? h.subscription.kinds : [h.subscription.kinds];
  if (!kinds.includes(event.event)) return;
  h.subscription.fn?.(event);
}

async function settle() {
  for (let i = 0; i < 8; i += 1) await Promise.resolve();
  await new Promise((r) => setTimeout(r, 0));
  for (let i = 0; i < 8; i += 1) await Promise.resolve();
}

beforeEach(() => {
  h.store.clear();
  h.subscription = { kinds: [], fn: null };
  h.appStateListeners = [];
  h.currentState = 'active';
  h.endpoint = CONN;
  h.connections = [CONN];
  h.fireMock.mockReset();
  h.fireMock.mockImplementation(async () => true);
  h.permMock.mockReset();
  h.permMock.mockImplementation(async () => 'granted');
  h.requestPermMock.mockReset();
  h.requestPermMock.mockImplementation(async () => 'granted');
  h.pollMock.mockReset();
  h.pollMock.mockImplementation(async () => ({ groups: 1, notifications: 0 }));
  h.primer = { open: false, onEnable: null, onDecline: null };
});

describe('NotificationBridge live delivery', () => {
  it('subscribes to exactly NOTIFIABLE_KINDS', () => {
    render(<NotificationBridge />);
    expect(h.subscription.kinds).toEqual(NOTIFIABLE_KINDS);
  });

  it('fires exactly one notification for a live notifiable event', async () => {
    render(<NotificationBridge />);
    emit({ event: 'agent.message', seq: 10, data: { profile: 'abby' } });
    await settle();

    expect(h.fireMock).toHaveBeenCalledTimes(1);
    expect(h.fireMock.mock.calls[0][0].seq).toBe(10);
  });

  it('fires nothing for a non-notifiable kind', async () => {
    render(<NotificationBridge />);
    emit({ event: 'wg.mention', seq: 11, data: {} });
    emit({ event: 'session_changed', seq: 12, data: {} });
    await settle();

    expect(h.fireMock).not.toHaveBeenCalled();
  });

  it('does not duplicate when the same event:seq arrives twice (live then replay)', async () => {
    render(<NotificationBridge />);
    const ev = { event: 'wg.done', seq: 30, data: { wg_id: 'wg1' } };
    emit(ev);
    await settle();
    emit({ ...ev });
    await settle();

    expect(h.fireMock).toHaveBeenCalledTimes(1);
  });

  it('never advances afterSeq — the poll cursor is untouched by the live path', async () => {
    await saveState('daemon:mac', {
      afterSeq: 5, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '',
    });
    render(<NotificationBridge />);
    emit({ event: 'agent.message', seq: 400, data: {} });
    await settle();

    const state = await loadState('daemon:mac');
    expect(state.afterSeq).toBe(5);
    expect(state.seenIds).toEqual(['agent.message:400']);
  });

  it('does not mark an event seen when scheduling the notification fails', async () => {
    h.fireMock.mockImplementation(async () => false);
    render(<NotificationBridge />);
    emit({ event: 'agent.message', seq: 41, data: {} });
    await settle();

    const state = await loadState('daemon:mac');
    expect(state.seenIds).toEqual([]);
  });

  it('does not notify an approval whose timeout has already elapsed', async () => {
    render(<NotificationBridge />);
    emit({
      event: 'approval.request',
      seq: 50,
      data: { ts: Date.now() / 1000 - 600, timeout_s: 60, command: 'rm -rf /' },
    });
    await settle();

    expect(h.fireMock).not.toHaveBeenCalled();
  });

  it('notifies an approval still inside its timeout', async () => {
    render(<NotificationBridge />);
    emit({
      event: 'approval.request',
      seq: 51,
      data: { ts: Date.now() / 1000, timeout_s: 60, command: 'rm -rf /' },
    });
    await settle();

    expect(h.fireMock).toHaveBeenCalledTimes(1);
  });

  it('ignores a frame with no usable seq rather than poisoning seenIds with "kind:"', async () => {
    render(<NotificationBridge />);
    emit({ event: 'agent.message', seq: null, data: {} });
    await settle();

    expect(h.fireMock).not.toHaveBeenCalled();
    const state = await loadState('daemon:mac');
    expect(state.seenIds).toEqual([]);
  });

  it('stays inert while no daemon is paired', async () => {
    h.endpoint = null;
    h.connections = [];
    render(<NotificationBridge />);
    emit({ event: 'agent.message', seq: 60, data: {} });
    await settle();

    expect(h.fireMock).not.toHaveBeenCalled();
    expect(h.pollMock).not.toHaveBeenCalled();
  });
});

describe('NotificationBridge catch-up', () => {
  it('runs catch-up once on mount', async () => {
    render(<NotificationBridge />);
    await settle();
    expect(h.pollMock).toHaveBeenCalledTimes(1);
  });

  it('runs catch-up again when the app returns to active, without overlapping the mount run', async () => {
    let release;
    const blocked = new Promise((r) => { release = r; });
    h.pollMock.mockImplementationOnce(async () => {
      await blocked;
      return { groups: 1, notifications: 0 };
    });

    render(<NotificationBridge />);
    await settle();
    expect(h.pollMock).toHaveBeenCalledTimes(1);

    // Resume while the mount run is still in flight: must not start a second one.
    h.appStateListeners.forEach((fn) => fn('active'));
    await settle();
    expect(h.pollMock).toHaveBeenCalledTimes(1);

    release();
    await settle();
  });

  it('ignores AppState transitions that are not active', async () => {
    render(<NotificationBridge />);
    await settle();
    h.pollMock.mockClear();

    h.appStateListeners.forEach((fn) => fn('background'));
    h.appStateListeners.forEach((fn) => fn('inactive'));
    await settle();

    expect(h.pollMock).not.toHaveBeenCalled();
  });
});

describe('NotificationBridge permission priming', () => {
  it('explains before it prompts — the OS dialog never fires straight from mount', async () => {
    h.permMock.mockImplementation(async () => 'undetermined');

    render(<NotificationBridge />);
    await settle();

    expect(h.primer.open).toBe(true);
    expect(h.requestPermMock).not.toHaveBeenCalled();
  });

  it('Enable notifications closes the primer, prompts, and catches up', async () => {
    h.permMock.mockImplementation(async () => 'undetermined');
    render(<NotificationBridge />);
    await settle();

    await h.primer.onEnable();
    await settle();

    expect(h.requestPermMock).toHaveBeenCalledTimes(1);
    expect(h.primer.open).toBe(false);
    expect(h.pollMock).toHaveBeenCalled();
  });

  it('Not now is remembered — the primer never reappears and the OS is never asked', async () => {
    h.permMock.mockImplementation(async () => 'undetermined');
    const first = render(<NotificationBridge />);
    await settle();

    await h.primer.onDecline();
    await settle();
    expect(h.primer.open).toBe(false);
    first.unmount();

    render(<NotificationBridge />);
    await settle();

    expect(h.primer.open).toBe(false);
    expect(h.requestPermMock).not.toHaveBeenCalled();
  });

  it('does not prime again once the user has accepted', async () => {
    h.permMock.mockImplementation(async () => 'undetermined');
    const first = render(<NotificationBridge />);
    await settle();
    await h.primer.onEnable();
    await settle();
    first.unmount();

    h.requestPermMock.mockClear();
    render(<NotificationBridge />);
    await settle();

    expect(h.primer.open).toBe(false);
    expect(h.requestPermMock).not.toHaveBeenCalled();
  });

  it('never primes when permission is already resolved', async () => {
    h.permMock.mockImplementation(async () => 'denied');
    render(<NotificationBridge />);
    await settle();

    expect(h.primer.open).toBe(false);
    expect(h.requestPermMock).not.toHaveBeenCalled();
  });
});

describe('NotificationBridge deferred permission', () => {
  it('Not now leaves delivery off, and enabling later in Settings starts it from that point', async () => {
    h.permMock.mockImplementation(async () => 'undetermined');
    const first = render(<NotificationBridge />);
    await settle();
    await h.primer.onDecline();
    await settle();

    emit({ event: 'agent.message', seq: 90, data: {} });
    await settle();
    expect(h.fireMock).not.toHaveBeenCalled();
    expect((await loadState('daemon:mac')).seenIds).toEqual([]);
    first.unmount();

    // The user turns it on later from Settings; the bridge remounts with permission granted.
    h.permMock.mockImplementation(async () => 'granted');
    render(<NotificationBridge />);
    await settle();

    emit({ event: 'agent.message', seq: 91, data: {} });
    await settle();

    expect(h.fireMock).toHaveBeenCalledTimes(1);
    expect(h.fireMock.mock.calls[0][0].seq).toBe(91);
  });
});

describe('NotificationBridge cross-path coordination', () => {
  it('a poll delivering the same event the stream already showed does not notify twice', async () => {
    const { deliverEvents } = await import('./deliver');
    render(<NotificationBridge />);
    const ev = { event: 'wg.done', seq: 77, data: { wg_id: 'wg1' } };

    emit(ev);
    await settle();
    expect(h.fireMock).toHaveBeenCalledTimes(1);

    await deliverEvents([ev], CONN);

    expect(h.fireMock).toHaveBeenCalledTimes(1);
    const state = await loadState('daemon:mac');
    expect(state.afterSeq).toBe(77);
  });
});
