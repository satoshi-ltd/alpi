import { useFocusEffect } from 'expo-router';
import { useCallback, useRef } from 'react';

import { useProfileAttention } from './useDaemonData';
import { useEventEffect } from './useEvents';

const REFETCH = ['attention.changed', 'memory_changed', 'schedule.changed', 'schedule.failed', 'schedule.done'];

export function useAttention(profile) {
  const inner = useProfileAttention(profile);
  const innerRefresh = inner.refresh;
  const innerInvalidate = inner.invalidate ?? inner.refresh;
  const refresh = useCallback(() => Promise.resolve(innerRefresh()).catch(() => {}), [innerRefresh]);
  const invalidate = useCallback(() => Promise.resolve(innerInvalidate()).catch(() => {}), [innerInvalidate]);
  const settled = useRef(false);
  useFocusEffect(useCallback(() => {
    if (settled.current) refresh();
    else settled.current = true;
  }, [refresh]));
  useEventEffect(REFETCH, (ev) => {
    if (!ev.data?.profile || ev.data.profile === profile) invalidate();
  });
  const att = inner.unsupported ? null : inner.data ?? null;
  return { att, refresh };
}
