import * as SecureStore from 'expo-secure-store';

const KEY = 'alpi.connections';
// Wiped on clearAll() so an old build's leftover token does not linger after unpair. Never read/migrated.
const LEGACY_ENDPOINT_KEY = 'alpi.endpoint';

function secureOpts() {
  try {
    if (SecureStore.AFTER_FIRST_UNLOCK !== undefined) {
      return { keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK };
    }
  } catch { /* */ }
  return {};
}

function genId() {
  return `c-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

function normalize(state) {
  if (!state || typeof state !== 'object') return { v: 1, active_id: null, connections: [] };
  const connections = Array.isArray(state.connections) ? state.connections.filter(isValidConnection) : [];
  let activeId = typeof state.active_id === 'string' ? state.active_id : null;
  if (activeId && !connections.find((c) => c.id === activeId)) {
    activeId = connections[0]?.id ?? null;
  }
  return { v: 1, active_id: activeId, connections };
}

function isValidConnection(c) {
  return c
    && typeof c.id === 'string'
    && typeof c.ip === 'string'
    && typeof c.port === 'number'
    && typeof c.token === 'string'
    && typeof c.name === 'string'
    && typeof c.deviceId === 'string'
    && c.deviceId.length > 0;
}

async function readRaw() {
  const raw = await SecureStore.getItemAsync(KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

async function writeRaw(state) {
  await SecureStore.setItemAsync(KEY, JSON.stringify(state), secureOpts());
}

export async function loadConnections() {
  const state = (await readRaw()) ?? { v: 1, active_id: null, connections: [] };
  return normalize(state);
}

export function sortConnectionsByRecency(connections) {
  return [...(connections ?? [])].sort(
    (a, b) => (b.last_connected ?? b.added_at ?? 0) - (a.last_connected ?? a.added_at ?? 0),
  );
}

export async function saveConnection(endpoint) {
  if (!endpoint?.deviceId || typeof endpoint.deviceId !== 'string') {
    throw new Error('saveConnection requires a deviceId — pair against an alpi daemon v0.6.6 or newer.');
  }
  const state = await loadConnections();
  const id = endpoint.id ?? genId();
  const conn = {
    id,
    name: endpoint.name ?? 'alpi',
    ip: endpoint.ip,
    port: endpoint.port,
    token: endpoint.token,
    kind: 'remote',
    added_at: Date.now(),
    last_connected: Date.now(),
    deviceId: endpoint.deviceId,
  };
  const existingIdx = state.connections.findIndex((c) => c.id === id);
  if (existingIdx >= 0) state.connections[existingIdx] = conn;
  else state.connections.push(conn);
  state.active_id = id;
  await writeRaw(state);
  return state;
}

export async function removeConnection(id) {
  const state = await loadConnections();
  state.connections = state.connections.filter((c) => c.id !== id);
  if (state.active_id === id) state.active_id = state.connections[0]?.id ?? null;
  await writeRaw(state);
  return state;
}

export async function setActiveConnection(id) {
  const state = await loadConnections();
  const conn = state.connections.find((c) => c.id === id);
  if (!conn) return state;
  conn.last_connected = Date.now();
  state.active_id = id;
  await writeRaw(state);
  return state;
}

export async function clearAll() {
  await SecureStore.deleteItemAsync(KEY);
  await SecureStore.deleteItemAsync(LEGACY_ENDPOINT_KEY);
}

export async function setDeviceIds(idToDeviceId) {
  const state = await loadConnections();
  let changed = false;
  for (const conn of state.connections) {
    const next = idToDeviceId.get(conn.id);
    if (next && conn.deviceId !== next) {
      conn.deviceId = next;
      changed = true;
    }
  }
  if (changed) await writeRaw(state);
  return state;
}
