// Status set: 'online' | 'offline' | 'disabled' | 'auth-failed' | 'rate-limited' | 'probing' | 'unknown'.

import Constants from 'expo-constants';
import { Platform } from 'react-native';
import { AUTH_FAILED, RpcError, call } from './rpc';
import { RATE_LIMITED } from './rateLimit';
import { endpointUrl } from './endpoint.js';

const PROBE_TIMEOUT_MS = 3500;
const VERSION_TIMEOUT_MS = 2000;
const registeredMetadata = new Set();

function registerMetadata(endpoint) {
  const key = `${endpointUrl(endpoint)}:${endpoint.token}`;
  if (registeredMetadata.has(key)) return;
  registeredMetadata.add(key);
  call(endpoint, 'host.connections.register_device', {
    client: 'mobile',
    name: Platform.constants?.Model || Platform.OS,
    app_version: Constants.expoConfig?.version || '',
  }, { timeoutMs: VERSION_TIMEOUT_MS }).catch(() => registeredMetadata.delete(key));
}

export async function probe(endpoint) {
  if (!endpoint) return { status: 'unknown', version: null, updateAvailable: null, deviceName: null, deviceId: null, role: null, connectionId: null, ownDeviceId: null, summaries: null };
  try {
    const summaries = await call(endpoint, 'host.profile.summaries', {}, { timeoutMs: PROBE_TIMEOUT_MS });
    let version = null;
    let updateAvailable = null;
    let deviceName = null;
    let deviceId = null;
    let role = null;
    let connectionId = null;
    let ownDeviceId = null;
    let installer = null;
    let selfUpdate = null;
    try {
      const res = await call(endpoint, 'host.version', {}, { timeoutMs: VERSION_TIMEOUT_MS });
      if (res && typeof res.version === 'string') version = res.version;
      if (res && typeof res.update_available === 'string' && res.update_available.trim()) {
        updateAvailable = res.update_available.trim();
      }
      if (res && typeof res.device_name === 'string' && res.device_name.trim()) {
        deviceName = res.device_name.trim();
      }
      if (res && typeof res.device_id === 'string' && res.device_id.trim()) {
        deviceId = res.device_id.trim();
      }
      if (res && typeof res.role === 'string' && res.role.trim()) {
        role = res.role.trim();
      }
      if (res && typeof res.connection_id === 'string' && res.connection_id.trim()) {
        connectionId = res.connection_id.trim();
      }
      if (res && typeof res.connection_device_id === 'string' && res.connection_device_id.trim()) {
        ownDeviceId = res.connection_device_id.trim();
      }
      if (res && typeof res.installer === 'string' && res.installer.trim()) {
        installer = res.installer.trim();
      }
      if (res && typeof res.self_update === 'boolean') {
        selfUpdate = res.self_update;
      }
      registerMetadata(endpoint);
    } catch {
      // version is non-fatal
    }
    return { status: 'online', version, updateAvailable, installer, selfUpdate, deviceName, deviceId, role, connectionId, ownDeviceId, summaries };
  } catch (e) {
    if (e instanceof RpcError && e.code === RATE_LIMITED) {
      return { status: 'rate-limited', version: null, updateAvailable: null, deviceName: null, deviceId: null, role: null, connectionId: null, ownDeviceId: null, summaries: null };
    }
    if (e instanceof RpcError && e.code === AUTH_FAILED) {
      if (e.data?.reason === 'connection-disabled') {
        return { status: 'disabled', version: null, updateAvailable: null, deviceName: null, deviceId: null, role: null, connectionId: null, ownDeviceId: null, summaries: null };
      }
      return { status: 'auth-failed', version: null, updateAvailable: null, deviceName: null, deviceId: null, role: null, connectionId: null, ownDeviceId: null, summaries: null };
    }
    return { status: 'offline', version: null, updateAvailable: null, deviceName: null, deviceId: null, role: null, connectionId: null, ownDeviceId: null, summaries: null };
  }
}

export async function probeAll(connections) {
  const status = new Map();
  const versions = new Map();
  const updates = new Map();
  const deviceIds = new Map();
  const roles = new Map();
  const identities = new Map();
  const installs = new Map();
  await Promise.all(
    connections.map(async (c) => {
      const r = await probe(c);
      status.set(c.id, r.status);
      if (r.version) versions.set(c.id, r.version);
      if (r.updateAvailable) updates.set(c.id, r.updateAvailable);
      if (r.installer || typeof r.selfUpdate === 'boolean') installs.set(c.id, { installer: r.installer ?? null, selfUpdate: r.selfUpdate ?? null });
      if (r.deviceId) deviceIds.set(c.id, r.deviceId);
      if (r.role) roles.set(c.id, r.role);
      if (r.connectionId || r.ownDeviceId) identities.set(c.id, { connectionId: r.connectionId, ownDeviceId: r.ownDeviceId });
    }),
  );
  return { status, versions, updates, installs, deviceIds, roles, identities };
}
