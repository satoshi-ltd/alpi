import { beforeEach, describe, expect, it, vi } from 'vitest';

const hoisted = vi.hoisted(() => ({
  scheduleMock: vi.fn(async () => 'notif-id'),
  categoryMock: vi.fn(async () => {}),
}));

vi.mock('expo-notifications', () => ({
  setNotificationHandler: vi.fn(),
  scheduleNotificationAsync: hoisted.scheduleMock,
  setNotificationCategoryAsync: hoisted.categoryMock,
  getPermissionsAsync: vi.fn(async () => ({ status: 'granted' })),
  requestPermissionsAsync: vi.fn(async () => ({ status: 'granted' })),
}));

import { _resetCategoriesForTests, fireForEvent, notificationIdFor, registerNotificationCategories } from './notify';

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

describe('notificationIdFor', () => {
  const ev = { event: 'wg.done', seq: 12 };

  it('is deterministic per daemon and sequence — the last-resort guard against a double banner', () => {
    expect(notificationIdFor(ev, { deviceId: 'mac', id: 'c1' })).toBe('aln:mac:wg.done:12');
    expect(notificationIdFor(ev, { deviceId: 'mac', id: 'c1' }))
      .toBe(notificationIdFor(ev, { deviceId: 'mac', id: 'c2' }));
  });

  it('separates daemons, kinds and sequences', () => {
    const base = notificationIdFor(ev, { deviceId: 'mac' });
    expect(notificationIdFor(ev, { deviceId: 'umbrel' })).not.toBe(base);
    expect(notificationIdFor({ event: 'agent.message', seq: 12 }, { deviceId: 'mac' })).not.toBe(base);
    expect(notificationIdFor({ event: 'wg.done', seq: 13 }, { deviceId: 'mac' })).not.toBe(base);
  });

  it('falls back to the connection id, then to a constant, without ever emitting an unsafe key', () => {
    expect(notificationIdFor(ev, { id: 'c1' })).toBe('aln:c1:wg.done:12');
    expect(notificationIdFor(ev, null)).toBe('aln:unknown:wg.done:12');
    expect(notificationIdFor({ event: 'wg.done', seq: null }, { deviceId: 'a b/c' })).toMatch(/^[\w:.-]+$/);
  });
});

describe('fireForEvent identifier', () => {
  it('passes the deterministic identifier to the scheduler', async () => {
    await fireForEvent({ event: 'wg.done', seq: 12, data: {} }, { deviceId: 'mac', name: 'home' });
    expect(hoisted.scheduleMock.mock.calls[0][0].identifier).toBe('aln:mac:wg.done:12');
  });

  it('reuses one identifier across repeated fires so a live/poll double-fire replaces', async () => {
    const ev = { event: 'wg.done', seq: 12, data: {} };
    const conn = { deviceId: 'mac' };
    await fireForEvent(ev, conn);
    await fireForEvent(ev, conn);
    expect(hoisted.scheduleMock.mock.calls[0][0].identifier)
      .toBe(hoisted.scheduleMock.mock.calls[1][0].identifier);
  });

  it('force makes each fire distinct — the dev screen needs to stack samples', async () => {
    const ev = { event: 'wg.done', seq: 12, data: {} };
    const conn = { deviceId: 'mac' };
    await fireForEvent(ev, conn, { force: true });
    await fireForEvent(ev, conn, { force: true });
    const [a, b] = hoisted.scheduleMock.mock.calls.map((c) => c[0].identifier);
    expect(a).not.toBe(b);
    expect(a.startsWith('aln:mac:wg.done:12:')).toBe(true);
  });
});

describe('actionable approvals', () => {
  const conn = { id: 'c1', name: 'home' };

  it('registers Deny and Allow once, both opening the app so the answer reaches the right daemon', async () => {
    _resetCategoriesForTests();
    hoisted.categoryMock.mockClear();
    await registerNotificationCategories();
    await registerNotificationCategories();
    expect(hoisted.categoryMock).toHaveBeenCalledTimes(1);
    const [category, actions] = hoisted.categoryMock.mock.calls[0];
    expect(category).toBe('alpi.approval');
    expect(actions.map((a) => [a.identifier, a.buttonTitle])).toEqual([['deny', 'Deny'], ['allow_once', 'Allow once']]);
    expect(actions.every((a) => a.options.opensAppToForeground === true)).toBe(true);
  });

  it('retries registration after a native failure', async () => {
    _resetCategoriesForTests();
    hoisted.categoryMock.mockClear();
    hoisted.categoryMock.mockRejectedValueOnce(new Error('not ready'));
    expect(await registerNotificationCategories()).toBe(false);
    expect(await registerNotificationCategories()).toBe(true);
    expect(hoisted.categoryMock).toHaveBeenCalledTimes(2);
  });

  it('attaches the category and the request id to an approval only', async () => {
    hoisted.scheduleMock.mockClear();
    await fireForEvent({ event: 'approval.request', seq: 3, data: { profile: 'builder', request_id: 'req-9', command: 'rm -rf dist' } }, conn);
    const approval = hoisted.scheduleMock.mock.calls[0][0].content;
    expect(approval.categoryIdentifier).toBe('alpi.approval');
    expect(approval.data.requestId).toBe('req-9');
    await fireForEvent({ event: 'clarification.request', seq: 4, data: { profile: 'doc', request_id: 'ask-1', question: 'Which one?' } }, conn);
    const question = hoisted.scheduleMock.mock.calls[1][0].content;
    expect(question.categoryIdentifier).toBeUndefined();
    expect(question.data.requestId).toBe('ask-1');
    expect(question.body).toBe('Which one?');
  });
});
