import { call } from '../../lib/rpc';
import { NOTIFIABLE_KINDS } from './kinds';
import { alnStateKey, loadState, recordSeen, saveState } from './state';

export { recordSeen };

// host.events.history returns the tail when >limit events since cursor — ALN surfaces the latest and skips ahead, no backfill of older missed events.
const POLL_LIMIT = 50;
const POLL_TIMEOUT_MS = 8000;

export const WAKE_BUDGET_MS = 25_000;

export async function pollConnection(connection, { now } = {}) {
  const nowMs = now ?? Date.now();
  const key = alnStateKey(connection);
  let state = await loadState(key);
  state.lastPollMs = nowMs;

  const newEvents = [];
  let ok = false;

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
    ok = true;
  } catch (e) {
    state.lastError = String(e?.message || e || 'poll failed');
  }

  await saveState(key, state);
  return { events: newEvents, state, ok };
}

export async function commitDelivered(stateKey, events) {
  let state = await loadState(stateKey);
  let cursor = state.afterSeq;
  for (const ev of events) {
    const evId = `${ev?.event || ''}:${ev?.seq ?? ''}`;
    state = recordSeen(state, evId);
    if (Number.isFinite(ev?.seq) && ev.seq > cursor) cursor = ev.seq;
  }
  state.afterSeq = cursor;
  await saveState(stateKey, state);
}
