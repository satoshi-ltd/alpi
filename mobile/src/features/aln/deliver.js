import { isStale } from './kinds';
import { fireForEvent, getPermissionStatus } from './notify';
import { alnStateKey, eventId, loadState, recordSeen, saveState, withStateLock } from './state';

const FIRE_TIMEOUT_MS = 5000;

// A hung native scheduler would otherwise wedge this daemon's lock, and with it every later poll.
function fireWithTimeout(event, connection) {
  return Promise.race([
    Promise.resolve().then(() => fireForEvent(event, connection)).catch(() => false),
    new Promise((resolve) => setTimeout(() => resolve(false), FIRE_TIMEOUT_MS)),
  ]);
}

// The one delivery decision per daemon: the seenIds re-check and the fire must sit inside the same lock, or a live frame and a poll page racing on the same event both schedule it.
export async function deliverEvents(events, connection, { advanceCursor = true, deadline = null, nextSeq = null } = {}) {
  const key = alnStateKey(connection);
  const page = Array.isArray(events) ? events : [];
  // nextSeq alone is enough work to do: it anchors a freshly paired daemon whose first page is empty.
  if (!key || (page.length === 0 && nextSeq === null)) return 0;
  // Without this the live path "delivers" into a denied permission, marks the events seen, and the poll then consumes them unseen.
  if (await getPermissionStatus() !== 'granted') return 0;

  return withStateLock(key, async () => {
    let state = await loadState(key);
    // Ascending, or a failed fire could break the batch below a higher seq the cursor already passed.
    const ordered = [...page].sort((a, b) => (a?.seq ?? 0) - (b?.seq ?? 0));

    const persist = async (next) => {
      state = next;
      try {
        await saveState(key, state);
        return true;
      } catch {
        return false;
      }
    };

    const consumed = (s, event) => (
      advanceCursor && Number.isFinite(event?.seq) && event.seq > s.afterSeq
        ? { ...s, afterSeq: event.seq }
        : s
    );

    // First contact with a daemon anchors the cursor instead of replaying its retained backlog.
    if (advanceCursor && !state.anchored) {
      const fromPage = ordered.reduce((max, e) => (Number.isFinite(e?.seq) && e.seq > max ? e.seq : max), state.afterSeq);
      const head = nextSeq !== null && nextSeq > fromPage ? nextSeq : fromPage;
      await persist({ ...state, afterSeq: head, anchored: true });
      return 0;
    }

    let fired = 0;
    for (const event of ordered) {
      if (deadline && Date.now() >= deadline) break;

      const id = eventId(event);
      if (!id) continue;

      if (state.seenIds.includes(id)) {
        const next = consumed(state, event);
        if (next !== state) await persist(next);
        continue;
      }

      if (isStale(event, Date.now())) {
        await persist(consumed(recordSeen(state, id), event));
        continue;
      }

      const ok = await fireWithTimeout(event, connection);
      // Stop the batch rather than skip: the cursor must stay below an event nobody was told about.
      if (!ok) break;

      // Persisted per event, so an OS kill mid-batch cannot replay what the user already saw.
      if (!await persist(consumed(recordSeen(state, id), event))) break;
      fired += 1;
    }

    return fired;
  });
}
