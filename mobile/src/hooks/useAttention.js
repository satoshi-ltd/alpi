import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';

import { useProfileAttention } from './useDaemonData';
import { useEventEffect } from './useEvents';

const REFETCH = ['attention.changed', 'memory_changed', 'schedule.changed', 'schedule.failed', 'schedule.done'];

export function useAttention(profile) {
  const inner = useProfileAttention(profile);
  const innerRefresh = inner.refresh;
  const running = useRef(false);
  const again = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);
  const refresh = useCallback(async () => {
    if (running.current) {
      again.current = true;
      return;
    }
    running.current = true;
    try {
      do {
        again.current = false;
        await Promise.resolve(innerRefresh()).catch(() => {});
      } while (again.current && alive.current);
    } finally {
      running.current = false;
    }
  }, [innerRefresh]);
  const settled = useRef(false);
  useFocusEffect(useCallback(() => {
    if (settled.current) refresh();
    else settled.current = true;
  }, [refresh]));
  useEventEffect(REFETCH, (ev) => {
    if (!ev.data?.profile || ev.data.profile === profile) refresh();
  });
  const att = inner.unsupported ? null : inner.data ?? null;
  return { att, refresh };
}
