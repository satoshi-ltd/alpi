import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { EndpointContext } from './EndpointContext';
import { clearImageCache } from '../hooks/useCachedImage';
import { seedCache } from '../hooks/useDaemonData';
import { probe, probeAll } from './probe';
import { call as rpcCall, callStream as rpcCallStream, dropEndpointPool } from './rpc';
import { clearAll, loadConnections, removeConnection, saveConnection, setActiveConnection, setDeviceIds } from './store';

const OFFLINE_REPROBE_MS = 4000;

// Rejected-token handling lives in <AuthFailedBridge> because it needs router and toast context.
export function EndpointProvider({ children }) {
  const [connections, setConnections] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [probeState, setProbeState] = useState(() => new Map());
  const [versionState, setVersionState] = useState(() => new Map());
  const [updateState, setUpdateState] = useState(() => new Map());
  const [roleState, setRoleState] = useState(() => new Map());
  const [ready, setReady] = useState(false);

  const activeEndpoint = useMemo(
    () => connections.find((c) => c.id === activeId) ?? null,
    [connections, activeId],
  );

  const probeByIdFrom = useCallback(async (list, id) => {
    const target = list.find((c) => c.id === id);
    if (!target) return 'unknown';
    setProbeState((m) => {
      const next = new Map(m);
      next.set(id, 'probing');
      return next;
    });
    const { status, version, updateAvailable, deviceId, role, summaries } = await probe(target);
    if (summaries) seedCache(id, 'host.profile.summaries', {}, summaries);
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
    setUpdateState((m) => {
      const next = new Map(m);
      if (updateAvailable) next.set(id, updateAvailable);
      else next.delete(id);
      return next;
    });
    setRoleState((m) => {
      const next = new Map(m);
      if (role) next.set(id, role);
      else next.delete(id);
      return next;
    });
    if (deviceId && deviceId !== target.deviceId) {
      const next = await setDeviceIds(new Map([[id, deviceId]]));
      setConnections(next.connections);
    }
    return status;
  }, []);

  // Cold-start probes ONLY the active; full-list probe lives in probeAllConnections (sheet on-open).
  const refresh = useCallback(async () => {
    const state = await loadConnections();
    setConnections(state.connections);
    setActiveId(state.active_id);
    setReady(true);
    if (state.active_id) {
      await probeByIdFrom(state.connections, state.active_id);
    }
  }, [probeByIdFrom]);

  const probeAllConnections = useCallback(async () => {
    const state = await loadConnections();
    setConnections(state.connections);
    setActiveId(state.active_id);
    setReady(true);
    const { status, versions, updates = new Map(), deviceIds, roles = new Map() } = await probeAll(state.connections);
    setProbeState(status);
    setVersionState(versions);
    setUpdateState(updates);
    setRoleState(roles);
    if (deviceIds.size > 0) {
      const next = await setDeviceIds(deviceIds);
      setConnections(next.connections);
    }
  }, []);

  useEffect(() => {
    refresh().catch(() => setReady(true));
  }, [refresh]);

  const connectionsRef = useRef(connections);
  connectionsRef.current = connections;

  // A dropped daemon has no liveness stream to recover on; terminal authentication states wait for user or host action.
  const activeStatus = activeId ? (probeState.get(activeId) ?? 'unknown') : null;
  useEffect(() => {
    if (!activeId) return undefined;
    if (activeStatus !== 'offline' && activeStatus !== 'unknown') return undefined;
    const timer = setInterval(() => {
      probeByIdFrom(connectionsRef.current, activeId).catch(() => {});
    }, OFFLINE_REPROBE_MS);
    return () => clearInterval(timer);
  }, [activeId, activeStatus, probeByIdFrom]);

  const setActive = useCallback(async (id) => {
    if (id === activeId) return;
    let list = connectionsRef.current;
    let target = list.find((c) => c.id === id);
    if (!target) {
      const state = await loadConnections();
      setConnections(state.connections);
      list = state.connections;
      target = list.find((c) => c.id === id);
    }
    if (!target) throw new Error(`unknown connection: ${id}`);
    // Drop the previous endpoint's pooled WS — its tokens won't auth on the new one and a stale socket holds an FD + battery for nothing.
    const prev = list.find((c) => c.id === activeId);
    if (prev) dropEndpointPool(prev);
    await setActiveConnection(id);
    setActiveId(id);
    probeByIdFrom(list, id).catch(() => {});
  }, [activeId, probeByIdFrom]);

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
    clearImageCache();
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

  const probeOne = useCallback(
    (id) => probeByIdFrom(connections, id),
    [connections, probeByIdFrom],
  );

  const markConnectionStatus = useCallback((id, status) => {
    if (!id) return;
    setProbeState((current) => {
      const next = new Map(current);
      next.set(id, status);
      return next;
    });
  }, []);

  const call = useCallback(
    (method, params, options) => {
      if (!activeEndpoint) {
        return Promise.reject(new Error('No active daemon endpoint'));
      }
      return rpcCall(activeEndpoint, method, params, options);
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

  const activeRole = activeId ? (roleState.get(activeId) ?? null) : null;
  const value = useMemo(
    () => ({
      ready,
      connections,
      activeId,
      endpoint: activeEndpoint,
      probeState,
      versionState,
      updateState,
      roleState,
      activeRole,
      setActive,
      addConnection,
      forget,
      unpair,
      probeOne,
      markConnectionStatus,
      probeAll: probeAllConnections,
      call,
      callStream,
    }),
    [ready, connections, activeId, activeEndpoint, probeState, versionState, updateState, roleState, activeRole, setActive, addConnection, forget, unpair, probeOne, markConnectionStatus, probeAllConnections, call, callStream],
  );

  return <EndpointContext.Provider value={value}>{children}</EndpointContext.Provider>;
}
