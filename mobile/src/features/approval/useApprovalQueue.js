import { useCallback, useEffect, useState } from 'react';

import { useEndpoint } from '../../lib/EndpointContext';
import { useEventEffect } from '../../hooks/useEvents';

function deadlineFor(req) {
  // Prefer the daemon's `ts` (request emission wall-clock, seconds since epoch) so a cold-start fetch 40s into a 60s window shows ~20s left, not 60s.
  if (typeof req.timeout_s !== 'number') return null;
  const window = Math.max(0, req.timeout_s * 1000);
  if (typeof req.ts === 'number') return req.ts * 1000 + window;
  return Date.now() + window;
}

function enqueueRequest(q, req) {
  if (!req?.request_id) return q;
  if (q.some((r) => r.request_id === req.request_id)) return q;
  return [
    ...q,
    {
      request_id: req.request_id,
      command: req.command || '',
      severity: req.severity || 'caution',
      pattern: req.pattern || '',
      profile: req.profile || null,
      deadline: deadlineFor(req),
    },
  ];
}

// Owns the pending-approval queue + the host.approval.respond RPC.
// Split from ApprovalSheet.jsx so the state machine can be unit-tested in
// jsdom without mounting RN primitives — the vitest setup mocks `react-native`
// loosely and rendering full RN views breaks under that shim.
export function useApprovalQueue() {
  const { call, endpoint } = useEndpoint();
  const [queue, setQueue] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEventEffect(['approval.request'], (ev) => {
    setQueue((q) => enqueueRequest(q, ev?.data ?? {}));
  });

  // Cold-start recovery: host.events.subscribe anchors at next_seq so a request emitted before mount never reaches the stream. Fetch pending whenever the endpoint changes.
  // ALSO drop the previous endpoint's queue first: a respond() against a stale entry would route through the NEW endpoint and hit `unknown or already resolved`, confusing the user.
  useEffect(() => {
    if (!endpoint) {
      setQueue([]);
      return undefined;
    }
    setQueue([]);
    let cancelled = false;
    call('host.approval.pending', {})
      .then((res) => {
        if (cancelled) return;
        const items = res?.requests ?? [];
        setQueue((q) => items.reduce(enqueueRequest, q));
      })
      .catch(() => { /* daemon may be offline or older */ });
    return () => { cancelled = true; };
  }, [endpoint, call]);

  useEventEffect(['approval.resolved'], (ev) => {
    const rid = ev?.data?.request_id;
    if (!rid) return;
    setQueue((q) => q.filter((r) => r.request_id !== rid));
  });

  const respond = useCallback(async (choice) => {
    const current = queue[0];
    if (!current || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await call('host.approval.respond', {
        request_id: current.request_id,
        choice,
      });
      if (res && res.ok === false) setError(res.reason || 'request no longer pending');
      setQueue((q) => q.filter((r) => r.request_id !== current.request_id));
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }, [busy, call, queue]);

  return { current: queue[0] ?? null, queue, busy, error, respond };
}
