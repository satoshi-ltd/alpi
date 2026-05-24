import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { EndpointContext } from './EndpointContext';
import { probe, probeAll } from './probe';
import { call as rpcCall, callStream as rpcCallStream, dropEndpointPool } from './rpc';
import { clearAll, loadConnections, removeConnection, saveConnection, setActiveConnection, setDeviceIds } from './store';

// auth-failed handling lives in <AuthFailedBridge> (app/_layout.jsx) — it needs router + toast context.
export function EndpointProvider({ children }) {
  const [connections, setConnections] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [probeState, setProbeState] = useState(() => new Map());
  const [versionState, setVersionState] = useState(() => new Map());
  const [ready, setReady] = useState(false);

  const activeEndpoint = useMemo(
    () => connections.find((c) => c.id === activeId) ?? null,
    [connections, activeId],
  );

  const refresh = useCallback(async () => {
    const state = await loadConnections();
    setConnections(state.connections);
    setActiveId(state.active_id);
    setReady(true);
    const { status, versions, deviceIds } = await probeAll(state.connections);
    setProbeState(status);
    setVersionState(versions);
    if (deviceIds.size > 0) {
      const next = await setDeviceIds(deviceIds);
      setConnections(next.connections);
    }
  }, []);

  useEffect(() => {
    refresh().catch(() => setReady(true));
  }, [refresh]);

  const setActive = useCallback(async (id) => {
    // Drop the previous endpoint's pooled WS — its tokens won't auth on the new one and a stale socket holds an FD + battery for nothing.
    const prev = connections.find((c) => c.id === activeId);
    if (prev) dropEndpointPool(prev);
    await setActiveConnection(id);
    setActiveId(id);
  }, [connections, activeId]);

  const addConnection = useCallback(async (endpoint) => {
    await saveConnection({ ...endpoint, added_at: Date.now() });
    await refresh();
  }, [refresh]);

  const forget = useCallback(async (id) => {
    const target = connections.find((c) => c.id === id);
    if (target) dropEndpointPool(target);
    await removeConnection(id);
    if (target?.deviceId) {
      const stillUsed = connections.some(
        (c) => c.id !== id && c.deviceId === target.deviceId,
      );
      if (!stillUsed) {
        try {
          const { alnStateKey, clearState } = await import('../features/aln/state');
          await clearState(alnStateKey(target));
        } catch { /* */ }
      }
    }
    await refresh();
  }, [refresh, connections]);

  const unpair = useCallback(async () => {
    for (const c of connections) dropEndpointPool(c);
    const targets = [...connections];
    await clearAll();
    try {
      const { alnStateKey, clearState } = await import('../features/aln/state');
      const cleared = new Set();
      for (const c of targets) {
        if (!c.deviceId) continue;
        const key = alnStateKey(c);
        if (cleared.has(key)) continue;
        cleared.add(key);
        await clearState(key);
      }
    } catch { /* */ }
    await refresh();
  }, [refresh, connections]);

  const probeOne = useCallback(async (id) => {
    const target = connections.find((c) => c.id === id);
    if (!target) return 'unknown';
    setProbeState((m) => {
      const next = new Map(m);
      next.set(id, 'probing');
      return next;
    });
    const { status, version, deviceId } = await probe(target);
    setProbeState((m) => {
      const next = new Map(m);
      next.set(id, status);
      return next;
    });
    setVersionState((m) => {
      const next = new Map(m);
      if (version) next.set(id, version);
      else next.delete(id);
      return next;
    });
    if (deviceId && deviceId !== target.deviceId) {
      const next = await setDeviceIds(new Map([[id, deviceId]]));
      setConnections(next.connections);
    }
    return status;
  }, [connections]);

  const call = useCallback(
    (method, params) => {
      if (!activeEndpoint) {
        return Promise.reject(new Error('No active daemon endpoint'));
      }
      return rpcCall(activeEndpoint, method, params);
    },
    [activeEndpoint],
  );

  const callStream = useCallback(
    (method, params, handlers) => {
      if (!activeEndpoint) {
        handlers?.onError?.(new Error('No active daemon endpoint'));
        return { cancel: () => {} };
      }
      return rpcCallStream(activeEndpoint, method, params, handlers);
    },
    [activeEndpoint],
  );

  const value = useMemo(
    () => ({
      ready,
      connections,
      activeId,
      endpoint: activeEndpoint,
      probeState,
      versionState,
      setActive,
      addConnection,
      forget,
      unpair,
      probeOne,
      probeAll: refresh,
      call,
      callStream,
    }),
    [ready, connections, activeId, activeEndpoint, probeState, versionState, setActive, addConnection, forget, unpair, probeOne, refresh, call, callStream],
  );

  return <EndpointContext.Provider value={value}>{children}</EndpointContext.Provider>;
}
