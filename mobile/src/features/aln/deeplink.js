import * as Notifications from 'expo-notifications';
import { useEffect } from 'react';
import { useRouter } from 'expo-router';

import { useEndpoint } from '../../lib/EndpointContext';

export function isForeignConnection(activeId, connectionId) {
  return !!connectionId && !!activeId && connectionId !== activeId;
}

export function routeFromResponse(response) {
  const data = response?.notification?.request?.content?.data || {};
  const link = typeof data.link === 'string' && data.link ? data.link : '/';
  const connectionId = typeof data.connectionId === 'string' ? data.connectionId : '';
  return { link, connectionId };
}

export async function applyResponse(response, { setActive, push }) {
  const { link, connectionId } = routeFromResponse(response);
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
}

// getLastNotificationResponseAsync returns the same launch response on every call — consume it once per process.
let coldStartConsumed = false;

export function useNotificationTapRouter() {
  const router = useRouter();
  const { setActive } = useEndpoint();
  useEffect(() => {
    let cancelled = false;
    const push = (link) => { if (!cancelled) router.push(link); };

    // A tap that cold-launches the killed app never reaches addNotificationResponseReceivedListener — only this does.
    if (!coldStartConsumed) {
      coldStartConsumed = true;
      Notifications.getLastNotificationResponseAsync?.()
        .then((response) => { if (response && !cancelled) applyResponse(response, { setActive, push }); })
        .catch(() => { /* */ });
    }

    const sub = Notifications.addNotificationResponseReceivedListener(async (response) => {
      await applyResponse(response, { setActive, push });
    });
    return () => {
      cancelled = true;
      try { sub?.remove?.(); } catch { /* */ }
    };
  }, [router, setActive]);
}
