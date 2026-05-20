// Status set: 'online' | 'offline' | 'auth-failed' | 'probing' | 'unknown'.

import { AUTH_FAILED, RpcError, call } from './rpc';

const PROBE_TIMEOUT_MS = 3500;
const VERSION_TIMEOUT_MS = 2000;

export async function probe(endpoint) {
  if (!endpoint) return { status: 'unknown', version: null };
  try {
    await call(endpoint, 'host.profile.summaries', {}, { timeoutMs: PROBE_TIMEOUT_MS });
    // Best-effort version fetch — pre-0.4.x daemons lack host.version, row just omits the chip.
    let version = null;
    try {
      const res = await call(endpoint, 'host.version', {}, { timeoutMs: VERSION_TIMEOUT_MS });
      if (res && typeof res.version === 'string') version = res.version;
    } catch {
      // version is non-fatal
    }
    return { status: 'online', version };
  } catch (e) {
    if (e instanceof RpcError && e.code === AUTH_FAILED) {
      return { status: 'auth-failed', version: null };
    }
    return { status: 'offline', version: null };
  }
}

export async function probeAll(connections) {
  const status = new Map();
  const versions = new Map();
  await Promise.all(
    connections.map(async (c) => {
      const r = await probe(c);
      status.set(c.id, r.status);
      if (r.version) versions.set(c.id, r.version);
    }),
  );
  return { status, versions };
}
