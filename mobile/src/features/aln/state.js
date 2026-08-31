import * as SecureStore from 'expo-secure-store';

const KEY_PREFIX = 'aln.state.';
const FLAG_PREFIX = 'aln.flag.';
const SEEN_CAP = 500;

export function alnStateKey(connection) {
  const id = connection?.deviceId;
  return id ? `daemon:${id}` : '';
}

export function eventId(event) {
  const kind = event?.event || '';
  const seq = event?.seq;
  if (!kind || !Number.isFinite(seq)) return '';
  return `${kind}:${seq}`;
}

function secureOpts() {
  try {
    if (SecureStore.AFTER_FIRST_UNLOCK !== undefined) {
      return { keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK };
    }
  } catch { /* */ }
  return {};
}

export function stateKey(connectionId) {
  return `${KEY_PREFIX}${String(connectionId).replace(/[^\w.-]/g, '_')}`;
}

export async function loadState(connectionId) {
  try {
    const raw = await SecureStore.getItemAsync(stateKey(connectionId));
    if (!raw) return defaultState();
    const parsed = JSON.parse(raw);
    const out = normalize(parsed);
    // A record written before `anchored` existed is an already-known daemon: only a MISSING record is a fresh pairing.
    if (parsed && typeof parsed === 'object' && typeof parsed.anchored !== 'boolean') out.anchored = true;
    return out;
  } catch {
    return defaultState();
  }
}

export async function saveState(connectionId, state) {
  await SecureStore.setItemAsync(
    stateKey(connectionId),
    JSON.stringify(normalize(state)),
    secureOpts(),
  );
}

export async function clearState(connectionId) {
  // Through the lock, or an in-flight delivery's save resurrects the record after an unpair.
  await withStateLock(connectionId, () => SecureStore.deleteItemAsync(stateKey(connectionId)));
}

// The live bridge and the background poll share one record per daemon; interleaved load-modify-save would drop whichever field the loser read before the winner wrote.
const _chains = new Map();

export function withStateLock(connectionId, fn) {
  const key = stateKey(connectionId);
  const prev = _chains.get(key) ?? Promise.resolve();
  const next = prev.then(fn, fn);
  _chains.set(key, next.then(() => {}, () => {}));
  return next;
}

export async function mutateState(connectionId, mutate) {
  return withStateLock(connectionId, async () => {
    const current = await loadState(connectionId);
    const next = await mutate(current);
    if (!next) return current;
    await saveState(connectionId, next);
    return next;
  });
}

export async function loadFlag(name, fallback = null) {
  try {
    const raw = await SecureStore.getItemAsync(`${FLAG_PREFIX}${name}`);
    if (raw === null || raw === undefined) return fallback;
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export async function saveFlag(name, value) {
  try {
    await SecureStore.setItemAsync(`${FLAG_PREFIX}${name}`, JSON.stringify(value), secureOpts());
  } catch { /* */ }
}

function defaultState() {
  return {
    afterSeq: 0,
    anchored: false,
    seenIds: [],
    lastPollMs: 0,
    lastSuccessMs: 0,
    lastError: '',
    degraded: false,
  };
}

function normalize(s) {
  const out = defaultState();
  if (s && typeof s === 'object') {
    if (Number.isFinite(s.afterSeq)) out.afterSeq = Number(s.afterSeq);
    if (typeof s.anchored === 'boolean') out.anchored = s.anchored;
    if (Array.isArray(s.seenIds)) out.seenIds = s.seenIds.slice(-SEEN_CAP);
    if (Number.isFinite(s.lastPollMs)) out.lastPollMs = Number(s.lastPollMs);
    if (Number.isFinite(s.lastSuccessMs)) out.lastSuccessMs = Number(s.lastSuccessMs);
    if (typeof s.lastError === 'string') out.lastError = s.lastError;
    if (typeof s.degraded === 'boolean') out.degraded = s.degraded;
  }
  return out;
}

export function recordSeen(state, eventId) {
  if (!eventId) return state;
  if (state.seenIds.includes(eventId)) return state;
  const next = state.seenIds.slice(-SEEN_CAP + 1);
  next.push(eventId);
  return { ...state, seenIds: next };
}
