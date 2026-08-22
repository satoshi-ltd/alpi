import { useEffect, useState } from 'react';

import { useEndpoint } from '../lib/EndpointContext';
import { useEventEffect } from './useEvents';

export function deadlineFor(req) {
  if (typeof req.timeout_s !== 'number') return null;
  const window = Math.max(0, req.timeout_s * 1000);
  if (typeof req.ts === 'number') return req.ts * 1000 + window;
  return Date.now() + window;
}

export function useRequestQueue(domain, enqueueRequest) {
  const { call, endpoint } = useEndpoint();
  const [queue, setQueue] = useState([]);

  useEventEffect([`${domain}.request`], (ev) => setQueue((q) => enqueueRequest(q, ev?.data ?? {})));

  useEffect(() => {
    setQueue([]);
    if (!endpoint) return undefined;
    let cancelled = false;
    call(`host.${domain}.pending`, {})
      .then((res) => {
        if (!cancelled) setQueue((q) => (res?.requests ?? []).reduce(enqueueRequest, q));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [endpoint, call]);

  useEventEffect([`${domain}.resolved`], (ev) => {
    const rid = ev?.data?.request_id;
    if (rid) setQueue((q) => q.filter((r) => r.request_id !== rid));
  });

  return { call, queue, setQueue };
}
