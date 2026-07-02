import { useCallback, useEffect, useRef, useState } from "react";

export function useSwrValue(cache, key, params, { enabled = true, defer = false, prefetched } = {}) {
  const prefetchedMode = prefetched !== undefined;
  const active = enabled && !prefetchedMode;
  const [, setTick] = useState(0);
  const [loading, setLoading] = useState(() => active && !defer && cache.get(key) === undefined);
  const paramsRef = useRef(params);
  paramsRef.current = params;

  // Sync reset on key flip — one render with the previous key's loading flag would leak into RefreshBar.
  const [trackedKey, setTrackedKey] = useState(key);
  if (trackedKey !== key) {
    setTrackedKey(key);
    setLoading(active && !defer && cache.get(key) === undefined);
  }

  useEffect(() => {
    if (!enabled) return undefined;
    if (prefetchedMode) {
      cache.seed(key, prefetched);
      setLoading(false);
      return undefined;
    }
    const unsub = cache.subscribe(key, () => setTick((t) => t + 1));
    if (defer) {
      setLoading(true);
      return unsub;
    }
    let cancelled = false;
    setLoading(true);
    cache.load(key, paramsRef.current).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
      unsub();
    };
  }, [cache, key, enabled, defer, prefetchedMode, prefetched]);

  const refresh = useCallback(() => {
    if (!enabled || prefetchedMode) return Promise.resolve(null);
    setLoading(true);
    return cache.load(key, paramsRef.current, { force: true }).finally(() => setLoading(false));
  }, [cache, key, enabled, prefetchedMode]);

  const data = prefetchedMode ? prefetched : active ? cache.get(key) : undefined;
  const error = active ? cache.errorOf(key) : null;
  return { data, error, loading, refresh };
}
