import { usePathname, useRouter } from 'expo-router';
import { useCallback, useRef } from 'react';

import { useToast } from '../../components/Toast';
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

  const runAgain = useCallback(async ({ profile, jobId }) => {
    const key = `${profile}/${jobId}`;
    if (inflight.current.has(key)) return;
    inflight.current.add(key);
    try {
      await call('host.schedule.fire', { profile, id: jobId });
      toast({ message: 'Running it again', kind: 'success', duration: 2000 });
      refresh?.();
    } catch (e) {
      toast({ message: String(e?.message ?? e), kind: 'danger', duration: 4000 });
    } finally {
      inflight.current.delete(key);
    }
  }, [call, toast, refresh]);

  return { open, runAgain };
}
