import { beforeEach, describe, expect, it, vi } from 'vitest';

const hoisted = vi.hoisted(() => ({
  scheduleMock: vi.fn(async () => 'notif-id'),
  appState: { currentState: 'background' },
}));

vi.mock('expo-notifications', () => ({
  setNotificationHandler: vi.fn(),
  scheduleNotificationAsync: hoisted.scheduleMock,
  getPermissionsAsync: vi.fn(async () => ({ status: 'granted' })),
  requestPermissionsAsync: vi.fn(async () => ({ status: 'granted' })),
}));

vi.mock('react-native', () => ({
  AppState: hoisted.appState,
}));

import { fireForEvent } from './notify';

beforeEach(() => {
  hoisted.scheduleMock.mockClear();
  hoisted.appState.currentState = 'background';
});

describe('fireForEvent foreground gating', () => {
  const ev = { event: 'wg.done', seq: 7, data: { profile: 'vera', wg_id: 'wg1', summary: 'task closed' } };
  const conn = { id: 'c1', name: 'home' };

  it('fires when app is in background', async () => {
    hoisted.appState.currentState = 'background';
    const fired = await fireForEvent(ev, conn);
    expect(fired).toBe(true);
    expect(hoisted.scheduleMock).toHaveBeenCalledTimes(1);
  });

  it('fires when app is inactive (transition state)', async () => {
    hoisted.appState.currentState = 'inactive';
    const fired = await fireForEvent(ev, conn);
    expect(fired).toBe(true);
    expect(hoisted.scheduleMock).toHaveBeenCalledTimes(1);
  });

  it('skips when app is active and force is not set', async () => {
    hoisted.appState.currentState = 'active';
    const fired = await fireForEvent(ev, conn);
    expect(fired).toBe(false);
    expect(hoisted.scheduleMock).not.toHaveBeenCalled();
  });

  it('fires when app is active and force is true', async () => {
    hoisted.appState.currentState = 'active';
    const fired = await fireForEvent(ev, conn, { force: true });
    expect(fired).toBe(true);
    expect(hoisted.scheduleMock).toHaveBeenCalledTimes(1);
  });
});

describe('fireForEvent notification payload', () => {
  it('carries link, connectionId, eventId, kind in data', async () => {
    hoisted.appState.currentState = 'background';
    const ev = { event: 'wg.done', seq: 12, data: { profile: 'vera', wg_id: 'wg-abc', summary: 'task closed' } };
    const conn = { id: 'c1', name: 'home' };

    await fireForEvent(ev, conn);

    const payload = hoisted.scheduleMock.mock.calls[0][0];
    expect(payload.content.data.link).toBe('/wg/wg-abc');
    expect(payload.content.data.connectionId).toBe('c1');
    expect(payload.content.data.eventId).toBe('wg.done:12');
    expect(payload.content.data.kind).toBe('wg.done');
    expect(payload.trigger).toBe(null);
  });
});
