import { useCallback, useState } from 'react';

import { deadlineFor, useRequestQueue } from '../../hooks/useRequestQueue';

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
      allow_other: !!req.allow_other && !multi,
      multi,
      deadline: deadlineFor(req),
    },
  ];
}

export function useClarificationQueue() {
  const { call, queue, setQueue } = useRequestQueue('clarification', enqueueRequest);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

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
  }, [busy, call, queue, setQueue]);

  const cancel = useCallback(() => respond('User cancelled clarification.'), [respond]);

  return { current: queue[0] ?? null, queue, busy, error, respond, cancel };
}
