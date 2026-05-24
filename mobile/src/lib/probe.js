// Status set: 'online' | 'offline' | 'auth-failed' | 'probing' | 'unknown'.

import { AUTH_FAILED, RpcError, call } from './rpc';

const PROBE_TIMEOUT_MS = 3500;
const VERSION_TIMEOUT_MS = 2000;

export async function probe(endpoint) {
  if (!endpoint) return { status: 'unknown', version: null, deviceName: null, deviceId: null };
  try {
    await call(endpoint, 'host.profile.summaries', {}, { timeoutMs: PROBE_TIMEOUT_MS });
    let version = null;
    let deviceName = null;
    let deviceId = null;
    try {
      const res = await call(endpoint, 'host.version', {}, { timeoutMs: VERSION_TIMEOUT_MS });
      if (res && typeof res.version === 'string') version = res.version;
      if (res && typeof res.device_name === 'string' && res.device_name.trim()) {
        deviceName = res.device_name.trim();
      }
      if (res && typeof res.device_id === 'string' && res.device_id.trim()) {
        deviceId = res.device_id.trim();
      }
    } catch {
      // version is non-fatal
    }
    return { status: 'online', version, deviceName, deviceId };
  } catch (e) {
    if (e instanceof RpcError && e.code === AUTH_FAILED) {
      return { status: 'auth-failed', version: null, deviceName: null, deviceId: null };
    }
    return { status: 'offline', version: null, deviceName: null, deviceId: null };
  }
}

export async function probeAll(connections) {
  const status = new Map();
  const versions = new Map();
  const deviceIds = new Map();
  await Promise.all(
    connections.map(async (c) => {
      const r = await probe(c);
      status.set(c.id, r.status);
      if (r.version) versions.set(c.id, r.version);
      if (r.deviceId) deviceIds.set(c.id, r.deviceId);
    }),
  );
  return { status, versions, deviceIds };
}
