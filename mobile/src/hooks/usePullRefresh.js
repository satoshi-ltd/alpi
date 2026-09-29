import { useCallback, useEffect, useRef, useState } from 'react';

export function usePullRefresh(refresh) {
  const [refreshing, setRefreshing] = useState(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh?.();
    } catch {
      return;
    } finally {
      if (alive.current) setRefreshing(false);
    }
  }, [refresh]);
  return { refreshing, onRefresh };
}
