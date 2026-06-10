import { beforeEach, describe, expect, it, vi } from 'vitest';

const hoisted = vi.hoisted(() => ({
  scheduleMock: vi.fn(async () => 'notif-id'),
}));

vi.mock('expo-notifications', () => ({
  setNotificationHandler: vi.fn(),
  scheduleNotificationAsync: hoisted.scheduleMock,
  getPermissionsAsync: vi.fn(async () => ({ status: 'granted' })),
  requestPermissionsAsync: vi.fn(async () => ({ status: 'granted' })),
}));

import { fireForEvent } from './notify';

beforeEach(() => {
  hoisted.scheduleMock.mockClear();
});

describe('fireForEvent always surfaces', () => {
  const ev = { event: 'wg.done', seq: 7, data: { profile: 'vera', wg_id: 'wg1', summary: 'task closed' } };
  const conn = { id: 'c1', name: 'home' };

  it('fires regardless of app state — deliberate pushes are never suppressed in foreground', async () => {
    const fired = await fireForEvent(ev, conn);
    expect(fired).toBe(true);
    expect(hoisted.scheduleMock).toHaveBeenCalledTimes(1);
  });
});

describe('fireForEvent notification payload', () => {
  it('carries link, connectionId, eventId, kind in data', async () => {
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
