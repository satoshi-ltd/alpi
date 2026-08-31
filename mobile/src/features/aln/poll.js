import { call } from '../../lib/rpc';
import { NOTIFIABLE_KINDS } from './kinds';
import { alnStateKey, loadState, mutateState } from './state';

// Must match HISTORY_MAX in alpi/host/events.py: the daemon clamps to it and tail-truncates, so anything lower discards recoverable events.
const POLL_LIMIT = 500;
export const POLL_TIMEOUT_MS = 8000;

export const WAKE_BUDGET_MS = 25_000;

export async function pollConnection(connection) {
  const key = alnStateKey(connection);
  const cursor = await loadState(key);

  // The whole page, seen events included: deliverEvents owns the dedupe, and dropping seen events here would leave afterSeq parked below them and re-download the page forever.
  let events = [];
  let nextSeq = null;
  let ok = false;
  let lastError = '';

  try {
    const resp = await call(
      connection,
      'host.events.history',
      { after_seq: cursor.afterSeq, limit: POLL_LIMIT, kinds: NOTIFIABLE_KINDS },
      { timeoutMs: POLL_TIMEOUT_MS },
    );
    events = Array.isArray(resp?.events) ? resp.events : [];
    if (Number.isFinite(resp?.next_seq)) nextSeq = resp.next_seq;
    // A daemon reimage restarts seq at 0; without this the cursor parks above the counter and filters everything out forever.
    if (nextSeq !== null && nextSeq < cursor.afterSeq) {
      await mutateState(key, (s) => ({ ...s, afterSeq: 0, anchored: true, seenIds: [] }));
    }
    ok = true;
  } catch (e) {
    lastError = String(e?.message || e || 'poll failed');
  }

  return { events, nextSeq, ok, error: lastError };
}

// Per daemon, not per route: a stale alternate route must not stamp its error over a sibling that reached the daemon.
export async function recordGroupHealth(connection, { ok, error, degraded = false }) {
  await mutateState(alnStateKey(connection), (s) => ({
    ...s,
    lastPollMs: Date.now(),
    lastSuccessMs: ok ? Date.now() : s.lastSuccessMs,
    lastError: ok ? '' : (error || s.lastError),
    degraded: ok ? degraded : s.degraded,
  }));
}
