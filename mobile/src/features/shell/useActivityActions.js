import { usePathname, useRouter } from 'expo-router';
import { useCallback, useRef } from 'react';

import { useToast } from '../../components/Toast';
import { isMissingVerb } from '../../hooks/useActivity';
import { focusRequest } from '../../hooks/useRequestQueue';
import { useEndpoint } from '../../lib/EndpointContext';
import { openVerb } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';

export function useActivityActions(refresh) {
  const router = useRouter();
  const pathname = usePathname();
  const { twoPane } = usePane();
  const toast = useToast();
  const { call } = useEndpoint();
  const inflight = useRef(new Set());

  const open = useCallback((target) => {
    if (target.type === 'request') {
      focusRequest(target.domain, target.requestId);
      return;
    }
    router[openVerb({ twoPane, pathname })](target.path);
  }, [router, twoPane, pathname]);

  const fireJob = useCallback(async ({ profile, jobId }, { quiet = false } = {}) => {
    const key = `${profile}/${jobId}`;
    if (inflight.current.has(key)) return { status: 'busy' };
    inflight.current.add(key);
    try {
      await call('host.schedule.fire', { profile, id: jobId });
      if (!quiet) toast({ message: 'Running it again', kind: 'success' });
      return { status: 'ok' };
    } catch (e) {
      if (isMissingVerb(e)) return { status: 'gone', error: e };
      toast({ message: String(e?.message ?? e), kind: 'danger' });
      return { status: 'failed', error: e };
    } finally {
      inflight.current.delete(key);
    }
  }, [call, toast]);

  const runAgain = useCallback(async (job) => {
    const { status, error } = await fireJob(job);
    if (status === 'ok') refresh?.();
    else if (status === 'gone') toast({ message: String(error?.message ?? error), kind: 'danger' });
  }, [fireJob, toast, refresh]);

  return { open, runAgain, fireJob };
}
