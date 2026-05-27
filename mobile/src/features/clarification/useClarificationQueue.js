import { useCallback, useEffect, useState } from 'react';

import { useEndpoint } from '../../lib/EndpointContext';
import { useEventEffect } from '../../hooks/useEvents';

function deadlineFor(req) {
  if (typeof req.timeout_s !== 'number') return null;
  const window = Math.max(0, req.timeout_s * 1000);
  if (typeof req.ts === 'number') return req.ts * 1000 + window;
  return Date.now() + window;
}

function enqueueRequest(q, req) {
  if (!req?.request_id) return q;
  const choices = Array.isArray(req.choices) ? req.choices : [];
  const cleanedChoices = choices
    .filter((c) => c && typeof c.label === 'string' && c.label.trim())
    .map((c) => ({
      label: String(c.label),
      description: typeof c.description === 'string' ? c.description : '',
    }));
  if (cleanedChoices.length < 2) return q;
  if (q.some((r) => r.request_id === req.request_id)) return q;
  const multi = !!req.multi;
  return [
    ...q,
    {
      request_id: req.request_id,
      profile: req.profile || null,
      question: req.question || '',
      choices: cleanedChoices,
      // Backend forces allow_other off for multi; mirror that defensively here.
      allow_other: !!req.allow_other && !multi,
      multi,
      deadline: deadlineFor(req),
    },
  ];
}

// Owns the pending clarification queue + host.clarification.respond RPC; state split from rendering for jsdom tests.
export function useClarificationQueue() {
  const { call, endpoint } = useEndpoint();
  const [queue, setQueue] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEventEffect(['clarification.request'], (ev) => {
    setQueue((q) => enqueueRequest(q, ev?.data ?? {}));
  });

  useEffect(() => {
    if (!endpoint) {
      setQueue([]);
      return undefined;
    }
    setQueue([]);
    let cancelled = false;
    call('host.clarification.pending', {})
      .then((res) => {
        if (cancelled) return;
        const items = res?.requests ?? [];
        setQueue((q) => items.reduce(enqueueRequest, q));
      })
      .catch(() => { /* daemon may be offline or older */ });
    return () => { cancelled = true; };
  }, [endpoint, call]);

  useEventEffect(['clarification.resolved'], (ev) => {
    const rid = ev?.data?.request_id;
    if (!rid) return;
    setQueue((q) => q.filter((r) => r.request_id !== rid));
  });

  const respond = useCallback(async (choice) => {
    const current = queue[0];
    if (!current || busy) return;
    const text = (choice || '').trim();
    if (!text) {
      setError('answer cannot be empty');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await call('host.clarification.respond', {
        request_id: current.request_id,
        choice: text,
      });
      // Server-side validation can reject; keep the request and surface the reason so the user can retry.
      if (res && res.ok === false) {
        setError(res.reason || 'request no longer pending');
        return;
      }
      setQueue((q) => q.filter((r) => r.request_id !== current.request_id));
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }, [busy, call, queue]);

  const cancel = useCallback(() => respond('User cancelled clarification.'), [respond]);

  return { current: queue[0] ?? null, queue, busy, error, respond, cancel };
}
