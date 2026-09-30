import { useCallback, useEffect, useRef, useState } from 'react';

import { dismissRequestNotifications } from '../features/aln/dismiss';
import { useEndpoint } from '../lib/EndpointContext';
import { useEventEffect } from './useEvents';

export function deadlineFor(req) {
  if (typeof req.timeout_s !== 'number') return null;
  const window = Math.max(0, req.timeout_s * 1000);
  if (typeof req.ts === 'number') return req.ts * 1000 + window;
  return Date.now() + window;
}

export function promote(queue, requestId) {
  const index = queue.findIndex((r) => r.request_id === requestId);
  if (index <= 0) return queue;
  return [queue[index], ...queue.slice(0, index), ...queue.slice(index + 1)];
}

const focusListeners = new Set();

export function focusRequest(domain, requestId, connectionId = null) {
  if (!domain || !requestId) return;
  for (const fn of focusListeners) fn(domain, requestId, connectionId);
}

export function useRequestQueue(domain, enqueueRequest) {
  const { call, endpoint } = useEndpoint();
  const endpointId = endpoint?.id ?? null;
  const [queue, setQueue] = useState([]);
  const [tick, setTick] = useState(0);
  const endpointRef = useRef(endpointId);
  endpointRef.current = endpointId;
  const wantedRef = useRef(null);
  const askedRef = useRef(null);
  const landedRef = useRef(null);

  useEventEffect([`${domain}.request`], (ev) => setQueue((q) => enqueueRequest(q, ev?.data ?? {})));

  const loadPending = useCallback((key) => {
    askedRef.current = key;
    call(`host.${domain}.pending`, {})
      .then((res) => {
        if (endpointRef.current !== key) return;
        setQueue((q) => (res?.requests ?? []).reduce(enqueueRequest, q));
        landedRef.current = key;
        setTick((n) => n + 1);
      })
      .catch(() => {
        if (endpointRef.current !== key) return;
        landedRef.current = key;
        setTick((n) => n + 1);
      });
  }, [call, domain, enqueueRequest]);

  useEffect(() => {
    setQueue([]);
    askedRef.current = null;
    landedRef.current = null;
    if (!endpoint) return;
    loadPending(endpointId);
  }, [endpoint, call]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const listener = (target, requestId, connectionId) => {
      if (target !== domain) return;
      wantedRef.current = { id: requestId, connectionId };
      askedRef.current = null;
      landedRef.current = null;
      setTick((n) => n + 1);
    };
    focusListeners.add(listener);
    return () => { focusListeners.delete(listener); };
  }, [domain]);

  // A focus from a notification names its connection and can land before the switch does: never give up on another connection's list.
  useEffect(() => {
    const target = wantedRef.current;
    if (!target) return;
    const wanted = target.id;
    if (queue[0]?.request_id === wanted) {
      wantedRef.current = null;
      return;
    }
    if (queue.some((r) => r.request_id === wanted)) {
      setQueue((q) => promote(q, wanted));
      return;
    }
    if (!endpointId || (target.connectionId && target.connectionId !== endpointId)) return;
    if (landedRef.current === endpointId) {
      wantedRef.current = null;
      return;
    }
    if (askedRef.current !== endpointId) loadPending(endpointId);
  }, [queue, tick, endpointId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEventEffect([`${domain}.resolved`], (ev) => {
    const rid = ev?.data?.request_id;
    if (!rid) return;
    setQueue((q) => q.filter((r) => r.request_id !== rid));
    dismissRequestNotifications(rid);
  });

  return { call, queue, setQueue };
}
