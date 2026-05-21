import * as Notifications from 'expo-notifications';
import { useEffect } from 'react';
import { useRouter } from 'expo-router';

import { useEndpoint } from '../../lib/EndpointContext';

export function useNotificationTapRouter() {
  const router = useRouter();
  const { setActive } = useEndpoint();
  useEffect(() => {
    const sub = Notifications.addNotificationResponseReceivedListener(async (response) => {
      try {
        const data = response?.notification?.request?.content?.data || {};
        const link = typeof data.link === 'string' && data.link ? data.link : '/';
        const connectionId = typeof data.connectionId === 'string' ? data.connectionId : '';
        if (connectionId && typeof setActive === 'function') {
          try { await setActive(connectionId); } catch { /* */ }
        }
        router.push(link);
      } catch { /* */ }
    });
    return () => {
      try { sub?.remove?.(); } catch { /* */ }
    };
  }, [router, setActive]);
}
