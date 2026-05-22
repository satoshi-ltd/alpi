import { call } from '../../lib/rpc';
import { NOTIFIABLE_KINDS } from './kinds';
import { loadState, recordSeen, saveState } from './state';

export { recordSeen };

// host.events.history returns the tail when >limit events since cursor — ALN surfaces the latest and skips ahead, no backfill of older missed events.
const POLL_LIMIT = 50;
const POLL_TIMEOUT_MS = 8000;

export const WAKE_BUDGET_MS = 25_000;

export async function pollConnection(connection, { now } = {}) {
  const nowMs = now ?? Date.now();
  let state = await loadState(connection.id);
  state.lastPollMs = nowMs;

  const newEvents = [];

  try {
    const resp = await call(
      connection,
      'host.events.history',
      { after_seq: state.afterSeq, limit: POLL_LIMIT, kinds: NOTIFIABLE_KINDS },
      { timeoutMs: POLL_TIMEOUT_MS },
    );
    const events = Array.isArray(resp?.events) ? resp.events : [];
    for (const ev of events) {
      const evId = `${ev?.event || ''}:${ev?.seq ?? ''}`;
      if (state.seenIds.includes(evId)) continue;
      newEvents.push(ev);
    }
    state.lastSuccessMs = Date.now();
    state.lastError = '';
  } catch (e) {
    state.lastError = String(e?.message || e || 'poll failed');
  }

  await saveState(connection.id, state);
  return { events: newEvents, state };
}

export async function commitDelivered(connectionId, events) {
  let state = await loadState(connectionId);
  let cursor = state.afterSeq;
  for (const ev of events) {
    const evId = `${ev?.event || ''}:${ev?.seq ?? ''}`;
    state = recordSeen(state, evId);
    if (Number.isFinite(ev?.seq) && ev.seq > cursor) cursor = ev.seq;
  }
  state.afterSeq = cursor;
  await saveState(connectionId, state);
}
