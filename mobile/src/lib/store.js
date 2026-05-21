// Storage: { v:1, active_id, connections: [{id,name,ip,port,token,kind:'remote',added_at}] }. Legacy single-endpoint `alpi.endpoint` migrates to id='paired' on first load.

import * as SecureStore from 'expo-secure-store';

const KEY = 'alpi.connections';
const LEGACY_KEY = 'alpi.endpoint';

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
    && typeof c.name === 'string';
}

async function readRaw() {
  const raw = await SecureStore.getItemAsync(KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

async function writeRaw(state) {
  await SecureStore.setItemAsync(KEY, JSON.stringify(state), secureOpts());
}

async function migrateLegacy() {
  const legacy = await SecureStore.getItemAsync(LEGACY_KEY);
  if (!legacy) return null;
  try {
    const ep = JSON.parse(legacy);
    if (!ep || typeof ep.ip !== 'string' || typeof ep.port !== 'number' || typeof ep.token !== 'string') {
      await SecureStore.deleteItemAsync(LEGACY_KEY);
      return null;
    }
    const conn = {
      id: 'paired',
      name: typeof ep.name === 'string' ? ep.name : 'alpi',
      ip: ep.ip,
      port: ep.port,
      token: ep.token,
      kind: 'remote',
      added_at: Date.now(),
    };
    const state = { v: 1, active_id: conn.id, connections: [conn] };
    await writeRaw(state);
    await SecureStore.deleteItemAsync(LEGACY_KEY);
    return state;
  } catch {
    return null;
  }
}

export async function loadConnections() {
  let state = await readRaw();
  if (!state) {
    const migrated = await migrateLegacy();
    state = migrated ?? { v: 1, active_id: null, connections: [] };
  }
  return normalize(state);
}

export async function saveConnection(endpoint) {
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
  if (!state.connections.find((c) => c.id === id)) return state;
  state.active_id = id;
  await writeRaw(state);
  return state;
}

export async function clearAll() {
  await SecureStore.deleteItemAsync(KEY);
  await SecureStore.deleteItemAsync(LEGACY_KEY);
}
