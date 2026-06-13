import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('expo-notifications', () => ({
  getLastNotificationResponseAsync: vi.fn(async () => null),
  addNotificationResponseReceivedListener: vi.fn(() => ({ remove: vi.fn() })),
}));

import { applyResponse, routeFromResponse } from './deeplink';

function responseWith(data) {
  return { notification: { request: { content: { data } } } };
}

describe('routeFromResponse', () => {
  it('extracts link + connectionId from notification data', () => {
    expect(routeFromResponse(responseWith({ link: '/wg/abc', connectionId: 'c2' }))).toEqual({
      link: '/wg/abc',
      connectionId: 'c2',
    });
  });

  it('falls back to root link and empty connectionId when missing', () => {
    expect(routeFromResponse(responseWith({}))).toEqual({ link: '/', connectionId: '' });
    expect(routeFromResponse(null)).toEqual({ link: '/', connectionId: '' });
  });

  it('ignores non-string link/connectionId', () => {
    expect(routeFromResponse(responseWith({ link: 42, connectionId: {} }))).toEqual({
      link: '/',
      connectionId: '',
    });
  });
});

describe('applyResponse', () => {
  let setActive;
  let push;
  beforeEach(() => {
    setActive = vi.fn(async () => {});
    push = vi.fn();
  });

  it('switches the originating connection before navigating', async () => {
    const order = [];
    setActive = vi.fn(async () => { order.push('setActive'); });
    push = vi.fn(() => { order.push('push'); });
    await applyResponse(responseWith({ link: '/chat/vera', connectionId: 'c2' }), { setActive, push });
    expect(setActive).toHaveBeenCalledWith('c2');
    expect(push).toHaveBeenCalledWith('/chat/vera?connectionId=c2');
    expect(order).toEqual(['setActive', 'push']);
  });

  it('navigates without switching when no connectionId', async () => {
    await applyResponse(responseWith({ link: '/outputs' }), { setActive, push });
    expect(setActive).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith('/outputs');
  });

  it('still navigates if setActive throws', async () => {
    setActive = vi.fn(async () => { throw new Error('unknown connection'); });
    await applyResponse(responseWith({ link: '/chat/x', connectionId: 'gone' }), { setActive, push });
    expect(push).toHaveBeenCalledWith('/chat/x?connectionId=gone');
  });
});
