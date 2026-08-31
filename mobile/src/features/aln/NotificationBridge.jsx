import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';

import { useEventEffect } from '../../hooks/useEvents';
import { useEndpoint } from '../../lib/EndpointContext';
import { runPollOnce } from './backgroundTask';
import { deliverEvents } from './deliver';
import { NOTIFIABLE_KINDS } from './kinds';
import { getPermissionStatus, requestPermission } from './notify';
import { NotificationPrimer } from './NotificationPrimer';
import { alnStateKey, eventId, loadFlag, saveFlag } from './state';

const CATCHUP_INTERVAL_MS = 30000;
const CATCHUP_MIN_GAP_MS = 10000;
const PRIMER_FLAG = 'notificationPrimer';

export function NotificationBridge() {
  const { endpoint, connections } = useEndpoint();
  const hasConnection = (connections?.length ?? 0) > 0;
  const endpointRef = useRef(endpoint);
  endpointRef.current = endpoint;
  const lastCatchupRef = useRef(0);
  const catchupBusyRef = useRef(false);
  const inFlightRef = useRef(new Set());
  const [primerOpen, setPrimerOpen] = useState(false);

  const catchUp = useCallback(async ({ force = false } = {}) => {
    if (catchupBusyRef.current) return;
    if (!force && Date.now() - lastCatchupRef.current < CATCHUP_MIN_GAP_MS) return;
    catchupBusyRef.current = true;
    lastCatchupRef.current = Date.now();
    try {
      await runPollOnce();
    } catch { /* */ } finally {
      catchupBusyRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!hasConnection) return undefined;
    let cancelled = false;
    (async () => {
      const status = await getPermissionStatus();
      if (cancelled) return;
      if (status === 'undetermined') {
        const answered = await loadFlag(PRIMER_FLAG, null);
        if (cancelled) return;
        if (!answered) {
          setPrimerOpen(true);
          return;
        }
      }
      await catchUp({ force: true });
    })();
    return () => { cancelled = true; };
  }, [hasConnection, catchUp]);

  const onPrimerEnable = useCallback(async () => {
    setPrimerOpen(false);
    await saveFlag(PRIMER_FLAG, 'accepted');
    await requestPermission();
    await catchUp({ force: true });
  }, [catchUp]);

  const onPrimerDecline = useCallback(async () => {
    setPrimerOpen(false);
    await saveFlag(PRIMER_FLAG, 'declined');
  }, []);

  useEffect(() => {
    if (!hasConnection) return undefined;
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active') catchUp();
    });
    const timer = setInterval(() => {
      if (AppState.currentState === 'active') catchUp();
    }, CATCHUP_INTERVAL_MS);
    return () => {
      sub?.remove?.();
      clearInterval(timer);
    };
  }, [hasConnection, catchUp]);

  useEventEffect(NOTIFIABLE_KINDS, (event) => {
    const connection = endpointRef.current;
    const key = alnStateKey(connection);
    const id = eventId(event);
    if (!key || !id) return;
    // Keyed by daemon too: an endpoint swap can put the same kind:seq on a different daemon's stream.
    const guard = `${key}|${id}`;
    if (inFlightRef.current.has(guard)) return;
    inFlightRef.current.add(guard);
    (async () => {
      try {
        await deliverEvents([event], connection, { advanceCursor: false });
      } catch { /* */ } finally {
        inFlightRef.current.delete(guard);
      }
    })();
  });

  return (
    <NotificationPrimer open={primerOpen} onEnable={onPrimerEnable} onDecline={onPrimerDecline} />
  );
}
