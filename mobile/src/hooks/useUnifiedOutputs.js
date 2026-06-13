import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useEndpoint } from '../lib/EndpointContext';
import { call as rpcCall } from '../lib/rpc';
import { useDebouncedCallback } from './useDebouncedCallback';
import { useEventEffect } from './useEvents';

const LIMIT = 100;
const PER_CALL_TIMEOUT_MS = 8000;

export function mergeOutputs(perConnection) {
  return perConnection
    .flat()
    .sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0));
}

export async function fetchConnectionOutputs(connection, status, rpc = rpcCall) {
  if (!connection?.ip || !connection?.port) return [];
  let profiles;
  try {
    const res = await rpc(connection, 'host.profile.summaries', {}, { timeoutMs: PER_CALL_TIMEOUT_MS });
    profiles = (res?.profiles ?? []).map((p) => ({ name: p.name, accent: p.accent ?? null }));
  } catch {
    return [];
  }
  if (profiles.length === 0) profiles = [{ name: 'default', accent: null }];
  const lists = await Promise.all(
    profiles.map((p) =>
      rpc(
        connection,
        'host.outputs.list',
        { profile: p.name, ...(status ? { status } : {}), limit: LIMIT },
        { timeoutMs: PER_CALL_TIMEOUT_MS },
      )
        .then((res) =>
          (res?.outputs ?? []).map((o) => ({
            ...o,
            profile: o.profile || p.name,
            accent: p.accent,
            connectionId: connection.id,
            connectionName: connection.name,
          })),
        )
        .catch(() => []),
    ),
  );
  return lists.flat();
}

// name+status in the signature so a rename or probe flip re-fans-out (re-tagging connectionName, dropping an offline daemon's stale rows).
export function connectionsSignature(connections, probeState) {
  const statusOf = (id) =>
    (probeState && typeof probeState.get === 'function' ? probeState.get(id) : undefined) ?? '';
  return (connections ?? [])
    .map((c) => `${c.id}:${c.name}:${c.ip}:${c.port}:${statusOf(c.id)}`)
    .join('|');
}

export function useUnifiedOutputs({ status } = {}) {
  const { connections, probeState } = useEndpoint();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const reqRef = useRef(0);

  const connSig = useMemo(
    () => connectionsSignature(connections, probeState),
    [connections, probeState],
  );

  const refresh = useCallback(async () => {
    if (connections.length === 0) {
      setRows([]);
      return;
    }
    const reqId = ++reqRef.current;
    setLoading(true);
    try {
      const perConn = await Promise.all(
        connections.map((c) => fetchConnectionOutputs(c, status).catch(() => [])),
      );
      if (reqId !== reqRef.current) return;
      setRows(mergeOutputs(perConn));
    } finally {
      if (reqId === reqRef.current) setLoading(false);
    }
  }, [connSig, status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Only the active connection streams events here; non-active deltas surface on next focus/refresh.
  const debouncedRefresh = useDebouncedCallback(refresh, 500);
  useEventEffect(['output.created', 'output.updated'], debouncedRefresh);

  return { rows, loading, refresh };
}

export async function markAllUnifiedRead(rows, connections, rpc = rpcCall) {
  const byId = new Map(connections.map((c) => [c.id, c]));
  const pairs = new Map();
  for (const r of rows) {
    const key = `${r.connectionId}:${r.profile}`;
    if (!pairs.has(key)) pairs.set(key, { connectionId: r.connectionId, profile: r.profile });
  }
  let total = 0;
  await Promise.all(
    Array.from(pairs.values()).map(async ({ connectionId, profile }) => {
      const conn = byId.get(connectionId);
      if (!conn) return;
      try {
        const res = await rpc(conn, 'host.outputs.mark_all_read', { profile });
        total += res?.count ?? 0;
      } catch {
        /* */
      }
    }),
  );
  return total;
}
