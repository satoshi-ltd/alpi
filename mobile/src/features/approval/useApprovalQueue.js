import { useCallback, useState } from 'react';

import { deadlineFor, useRequestQueue } from '../../hooks/useRequestQueue';

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
      cwd: req.cwd || null,
      deadline: deadlineFor(req),
    },
  ];
}

export function useApprovalQueue() {
  const { call, queue, setQueue } = useRequestQueue('approval', enqueueRequest);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

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
  }, [busy, call, queue, setQueue]);

  return { current: queue[0] ?? null, queue, busy, error, respond };
}
