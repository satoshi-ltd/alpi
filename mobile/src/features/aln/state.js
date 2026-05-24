import * as SecureStore from 'expo-secure-store';

const KEY_PREFIX = 'aln.state.';
const SEEN_CAP = 500;

export function alnStateKey(connection) {
  const id = connection?.deviceId;
  return id ? `daemon:${id}` : '';
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
  return `${KEY_PREFIX}${connectionId}`;
}

export async function loadState(connectionId) {
  try {
    const raw = await SecureStore.getItemAsync(stateKey(connectionId));
    if (!raw) return defaultState();
    return normalize(JSON.parse(raw));
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
  await SecureStore.deleteItemAsync(stateKey(connectionId));
}

function defaultState() {
  return {
    afterSeq: 0,
    seenIds: [],
    lastPollMs: 0,
    lastSuccessMs: 0,
    lastError: '',
  };
}

function normalize(s) {
  const out = defaultState();
  if (s && typeof s === 'object') {
    if (Number.isFinite(s.afterSeq)) out.afterSeq = Number(s.afterSeq);
    if (Array.isArray(s.seenIds)) out.seenIds = s.seenIds.slice(-SEEN_CAP);
    if (Number.isFinite(s.lastPollMs)) out.lastPollMs = Number(s.lastPollMs);
    if (Number.isFinite(s.lastSuccessMs)) out.lastSuccessMs = Number(s.lastSuccessMs);
    if (typeof s.lastError === 'string') out.lastError = s.lastError;
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
