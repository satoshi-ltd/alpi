import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('expo-notifications', () => ({
  getLastNotificationResponseAsync: vi.fn(async () => null),
  addNotificationResponseReceivedListener: vi.fn(() => ({ remove: vi.fn() })),
}));

vi.mock('../../components/Toast', () => ({ useToast: () => () => {} }));

import {
  applyResponse,
  isForeignConnection,
  requestFromResponse,
  resolveConnection,
  respondFromNotification,
  routeFromResponse,
  STALE_REQUEST_TOAST,
} from './deeplink';

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

describe('isForeignConnection', () => {
  it('is true only when both ids are set and differ', () => {
    expect(isForeignConnection('a', 'b')).toBe(true);
    expect(isForeignConnection('a', 'a')).toBe(false);
    expect(isForeignConnection('a', '')).toBe(false);
    expect(isForeignConnection(null, 'b')).toBe(false);
    expect(isForeignConnection(undefined, undefined)).toBe(false);
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

  it('fails closed: does NOT navigate when setActive rejects (connection gone)', async () => {
    setActive = vi.fn(async () => { throw new Error('unknown connection'); });
    await applyResponse(responseWith({ link: '/chat/x', connectionId: 'gone' }), { setActive, push });
    expect(setActive).toHaveBeenCalledWith('gone');
    expect(push).not.toHaveBeenCalled();
  });

  it('fails closed: does NOT navigate to a connection-scoped link with no way to switch', async () => {
    await applyResponse(responseWith({ link: '/chat/x', connectionId: 'c9' }), { setActive: undefined, push });
    expect(push).not.toHaveBeenCalled();
  });
});

function approvalResponse(actionIdentifier, data = {}) {
  return {
    actionIdentifier,
    notification: { request: { content: { data: { link: '/', connectionId: 'c2', kind: 'approval.request', requestId: 'req-1', ...data } } } },
  };
}

describe('requestFromResponse', () => {
  it('maps the two approval actions to their choices and a plain tap to none', () => {
    expect(requestFromResponse(approvalResponse('deny'))).toEqual({ domain: 'approval', requestId: 'req-1', choice: 'deny' });
    expect(requestFromResponse(approvalResponse('allow_once'))).toEqual({ domain: 'approval', requestId: 'req-1', choice: 'once' });
    expect(requestFromResponse(approvalResponse('expo.modules.notifications.actions.DEFAULT')).choice).toBeNull();
    expect(requestFromResponse(approvalResponse('constructor')).choice).toBeNull();
  });

  it('reads a clarification as a request with no inline answer', () => {
    const res = approvalResponse('allow_once', { kind: 'clarification.request', requestId: '', rawData: { request_id: 'ask-1' } });
    expect(requestFromResponse(res)).toEqual({ domain: 'clarification', requestId: 'ask-1', choice: null });
  });

  it('ignores every other kind', () => {
    expect(requestFromResponse(responseWith({ kind: 'wg.done', requestId: 'x' }))).toBeNull();
  });
});

describe('applyResponse with an actionable approval', () => {
  it('answers on the originating connection without opening a screen', async () => {
    const respond = vi.fn(async () => ({ ok: true }));
    const setActive = vi.fn(async () => {});
    const push = vi.fn();
    const focus = vi.fn();
    await applyResponse(approvalResponse('allow_once'), { setActive, push, respond, focus });
    expect(respond).toHaveBeenCalledWith('c2', 'req-1', 'once');
    expect(setActive).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it('falls back to the sheet when the answer cannot be delivered', async () => {
    const respond = vi.fn(async () => { throw new Error('offline'); });
    const push = vi.fn();
    const focus = vi.fn();
    await applyResponse(approvalResponse('deny'), { setActive: vi.fn(async () => {}), push, respond, focus });
    expect(push).toHaveBeenCalledWith('/?connectionId=c2');
    expect(focus).toHaveBeenCalledWith('approval', 'req-1', 'c2');
  });

  it('opens the right sheet on a plain tap, after switching to its connection', async () => {
    const order = [];
    const setActive = vi.fn(async () => { order.push('setActive'); });
    const push = vi.fn(() => order.push('push'));
    const focus = vi.fn(() => order.push('focus'));
    await applyResponse(approvalResponse(undefined, { kind: 'clarification.request', requestId: 'ask-1' }), { setActive, push, focus, respond: vi.fn() });
    expect(focus).toHaveBeenCalledWith('clarification', 'ask-1', 'c2');
    expect(order).toEqual(['setActive', 'push', 'focus']);
  });
});

describe('an approval answered too late', () => {
  it('says so and opens the app where the user can see what happened', async () => {
    const notify = vi.fn();
    const push = vi.fn();
    const focus = vi.fn();
    const respond = vi.fn(async () => ({ ok: false, reason: 'request no longer pending' }));
    await applyResponse(approvalResponse('allow_once'), { setActive: vi.fn(async () => {}), push, respond, focus, notify });
    expect(notify).toHaveBeenCalledWith(STALE_REQUEST_TOAST);
    expect(push).toHaveBeenCalledWith('/?connectionId=c2');
    expect(focus).toHaveBeenCalledWith('approval', 'req-1', 'c2');
  });

  it('stays quiet on a delivered answer', async () => {
    const notify = vi.fn();
    await applyResponse(approvalResponse('deny'), { setActive: vi.fn(), push: vi.fn(), respond: vi.fn(async () => ({ ok: true })), notify });
    expect(notify).not.toHaveBeenCalled();
  });
});

describe('answering from a cold start', () => {
  const stored = { connections: [{ id: 'c2', name: 'casa' }] };

  it('reads the stored connections when the provider has not loaded them yet', async () => {
    const load = vi.fn(async () => stored);
    expect(await resolveConnection('c2', { connections: [], load })).toEqual({ id: 'c2', name: 'casa' });
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('skips the store once the provider knows the connection', async () => {
    const load = vi.fn(async () => stored);
    expect(await resolveConnection('c2', { connections: [{ id: 'c2', name: 'live' }], load })).toEqual({ id: 'c2', name: 'live' });
    expect(load).not.toHaveBeenCalled();
  });

  it('answers on the stored connection, clears the banner and hands back the daemon reply', async () => {
    const call = vi.fn(async () => ({ ok: true }));
    const dismiss = vi.fn();
    const res = await respondFromNotification('c2', 'req-1', 'once', { connections: [], endpoint: null }, { call, load: async () => stored, dismiss });
    expect(call).toHaveBeenCalledWith({ id: 'c2', name: 'casa' }, 'host.approval.respond', { request_id: 'req-1', choice: 'once' });
    expect(dismiss).toHaveBeenCalledWith('req-1');
    expect(res).toEqual({ ok: true });
  });

  it('fails loudly for a connection that no longer exists, so the sheet takes over', async () => {
    await expect(respondFromNotification('gone', 'req-1', 'deny', { connections: [] }, { call: vi.fn(), load: async () => stored, dismiss: vi.fn() }))
      .rejects.toThrow('unknown connection');
  });
});
