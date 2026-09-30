import * as Notifications from 'expo-notifications';
import { useEffect, useRef } from 'react';
import { useRouter } from 'expo-router';

import { useToast } from '../../components/Toast';
import { focusRequest } from '../../hooks/useRequestQueue';
import { useEndpoint } from '../../lib/EndpointContext';
import { call as rpcCall } from '../../lib/rpc';
import { loadConnections } from '../../lib/store';
import { dismissRequestNotifications } from './dismiss';
import { APPROVAL_ACTIONS, requestDomain } from './kinds';

export function isForeignConnection(activeId, connectionId) {
  return !!connectionId && !!activeId && connectionId !== activeId;
}

export function routeFromResponse(response) {
  const data = response?.notification?.request?.content?.data || {};
  const link = typeof data.link === 'string' && data.link ? data.link : '/';
  const connectionId = typeof data.connectionId === 'string' ? data.connectionId : '';
  return { link, connectionId };
}

export function requestFromResponse(response) {
  const data = response?.notification?.request?.content?.data || {};
  const domain = requestDomain(data.kind);
  const requestId = typeof data.requestId === 'string' && data.requestId
    ? data.requestId
    : typeof data.rawData?.request_id === 'string' ? data.rawData.request_id : '';
  if (!domain || !requestId) return null;
  const action = response?.actionIdentifier;
  const choice = domain === 'approval' && Object.hasOwn(APPROVAL_ACTIONS, action ?? '') ? APPROVAL_ACTIONS[action] : null;
  return { domain, requestId, choice };
}

export const STALE_REQUEST_TOAST = { title: 'Already answered or expired', message: 'The agent is no longer waiting on this request.', duration: 2600 };

export async function applyResponse(response, { setActive, push, respond, focus = focusRequest, notify }) {
  const { link, connectionId } = routeFromResponse(response);
  const request = requestFromResponse(response);
  if (request?.choice && typeof respond === 'function') {
    let res;
    try {
      res = await respond(connectionId, request.requestId, request.choice);
    } catch {
      res = undefined;
    }
    if (res && res.ok !== false) return;
    if (res?.ok === false) notify?.(STALE_REQUEST_TOAST);
  }
  if (connectionId) {
    if (typeof setActive !== 'function') return;
    try {
      await setActive(connectionId);
    } catch {
      return;
    }
  }
  const href = connectionId
    ? `${link}${link.includes('?') ? '&' : '?'}connectionId=${encodeURIComponent(connectionId)}`
    : link;
  push?.(href);
  if (request) focus?.(request.domain, request.requestId, connectionId || null);
}

// getLastNotificationResponseAsync returns the same launch response on every call — consume it once per process.
let coldStartConsumed = false;

// A cold start from an action button runs before EndpointProvider has read the store, so the in-memory list can still be empty.
export async function resolveConnection(connectionId, { connections, endpoint, load = loadConnections } = {}) {
  if (!connectionId) return endpoint ?? null;
  const hit = (connections ?? []).find((c) => c.id === connectionId);
  if (hit) return hit;
  try {
    const state = await load();
    return (state?.connections ?? []).find((c) => c.id === connectionId) ?? null;
  } catch {
    return null;
  }
}

export async function respondFromNotification(connectionId, requestId, choice, known, { call = rpcCall, load, dismiss = dismissRequestNotifications } = {}) {
  const target = await resolveConnection(connectionId, { ...known, load });
  if (!target) throw new Error('unknown connection');
  const res = (await call(target, 'host.approval.respond', { request_id: requestId, choice })) ?? { ok: true };
  dismiss(requestId);
  return res;
}

export function useNotificationTapRouter() {
  const router = useRouter();
  const toast = useToast();
  const { setActive, connections, endpoint } = useEndpoint();
  const known = useRef({ connections, endpoint });
  known.current = { connections, endpoint };
  useEffect(() => {
    let cancelled = false;
    const push = (link) => { if (!cancelled) router.push(link); };
    const respond = (connectionId, requestId, choice) => respondFromNotification(connectionId, requestId, choice, known.current);
    const notify = (message) => toast(message);

    // A tap that cold-launches the killed app never reaches addNotificationResponseReceivedListener — only this does.
    if (!coldStartConsumed) {
      coldStartConsumed = true;
      Notifications.getLastNotificationResponseAsync?.()
        .then((response) => { if (response && !cancelled) applyResponse(response, { setActive, push, respond, notify }); })
        .catch(() => { /* */ });
    }

    const sub = Notifications.addNotificationResponseReceivedListener(async (response) => {
      await applyResponse(response, { setActive, push, respond, notify });
    });
    return () => {
      cancelled = true;
      try { sub?.remove?.(); } catch { /* */ }
    };
  }, [router, setActive, toast]);
}
