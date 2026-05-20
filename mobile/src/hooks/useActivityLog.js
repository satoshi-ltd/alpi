import { useEffect, useState } from 'react';

import { useEndpoint } from '../lib/EndpointContext';
import { useEvents } from './useEvents';

const MAX_HISTORY = 200;

// User-facing event whitelist (refresh-only events like session_changed excluded). Some are forward-compat: daemon doesn't fire wg.post/wg.task/wg.skip/mention/peer.pairing_request/daemon.offline yet.
const USER_FACING = new Set([
  'wg.done',
  'schedule.done',
  'schedule.failed',
  'budget.threshold',
  'wg.post',
  'wg.task',
  'wg.skip',
  'mention',
  'peer.pairing_request',
  'daemon.offline',
]);

function isUserFacing(ev) {
  return !!ev?.event && USER_FACING.has(ev.event);
}

function dedupKey(ev) {
  return `${ev.event}|${ev.at ?? ''}|${JSON.stringify(ev.data ?? {})}`;
}

export function useActivityLog() {
  const { endpoint, call } = useEndpoint();
  const { last } = useEvents();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!endpoint) {
      setHistory([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    call('host.events.history', { limit: MAX_HISTORY })
      .then((res) => {
        if (cancelled) return;
        setHistory((res?.events ?? []).filter(isUserFacing));
      })
      .catch(() => {
        if (!cancelled) setHistory([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [endpoint, call]);

  useEffect(() => {
    if (!last || !isUserFacing(last)) return;
    setHistory((cur) => {
      const key = dedupKey(last);
      if (cur.some((e) => dedupKey(e) === key)) return cur;
      const next = [...cur, last];
      return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next;
    });
  }, [last]);

  return { history, loading };
}
