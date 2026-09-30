import { useCallback, useEffect, useRef, useState } from 'react';

import { useToast } from '../components/Toast';
import { selection } from '../lib/haptics';

export function usePullRefresh(refresh) {
  const toast = useToast();
  const [refreshing, setRefreshing] = useState(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const onRefresh = useCallback(async () => {
    selection();
    setRefreshing(true);
    try {
      await refresh?.();
    } catch (e) {
      toast({ title: 'Refresh failed', message: String(e?.message ?? e), duration: 2600 });
    } finally {
      if (alive.current) setRefreshing(false);
    }
  }, [refresh]);
  return { refreshing, onRefresh };
}
