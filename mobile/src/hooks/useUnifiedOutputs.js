import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useEndpoint } from '../lib/EndpointContext';
import { endpointUrl } from '../lib/endpoint.js';
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

// Members can't list outputs (daemon rejects) — never ask; roleState is empty pre-probe, so a connection joins the fan-out only once probed admin.
export function adminConnectionsOf(connections, roleState) {
  return (connections ?? []).filter((c) => roleState?.get?.(c.id) === 'admin');
}

export function isMemberOnly(endpoint, connections, roleState) {
  const list = connections ?? [];
  return !!endpoint && list.length > 0 && list.every((c) => roleState?.get?.(c.id) === 'member');
}

export async function fetchConnectionOutputs(connection, status, rpc = rpcCall) {
  if (!endpointUrl(connection)) return { rows: [], ok: false };
  let profiles;
  try {
    const res = await rpc(connection, 'host.profile.summaries', {}, { timeoutMs: PER_CALL_TIMEOUT_MS });
    profiles = (res?.profiles ?? []).map((p) => ({ name: p.name, accent: p.accent ?? null }));
  } catch {
    return { rows: [], ok: false };
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
        .catch(() => null),
    ),
  );
  return { rows: lists.filter(Boolean).flat(), ok: lists.every(Boolean) };
}

// name+status in the signature so a rename or probe flip re-fans-out (re-tagging connectionName, dropping an offline daemon's stale rows).
export function connectionsSignature(connections, probeState) {
  const statusOf = (id) =>
    (probeState && typeof probeState.get === 'function' ? probeState.get(id) : undefined) ?? '';
  return (connections ?? [])
    .map((c) => `${c.id}:${c.name}:${endpointUrl(c)}:${statusOf(c.id)}`)
    .join('|');
}

export function useUnifiedOutputs({ status } = {}) {
  const { connections, probeState, roleState } = useEndpoint();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [unreachable, setUnreachable] = useState(false);
  const [unreachableCount, setUnreachableCount] = useState(0);
  const reqRef = useRef(0);

  const adminConnections = useMemo(
    () => adminConnectionsOf(connections, roleState),
    [connections, roleState],
  );
  const connSig = useMemo(
    () => connectionsSignature(adminConnections, probeState),
    [adminConnections, probeState],
  );

  const refresh = useCallback(async () => {
    // Bump the token even on the empty path: a fetch started while admin must not restore rows after a demotion drops the last admin.
    const reqId = ++reqRef.current;
    if (adminConnections.length === 0) {
      setRows([]);
      setUnreachable(false);
      setUnreachableCount(0);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const results = await Promise.all(
        adminConnections.map((c) =>
          fetchConnectionOutputs(c, status).catch(() => ({ rows: [], ok: false })),
        ),
      );
      if (reqId !== reqRef.current) return;
      setRows(mergeOutputs(results.map((r) => r.rows)));
      setUnreachable(results.some((r) => !r.ok));
      setUnreachableCount(results.filter((r) => !r.ok).length);
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

  return {
    rows,
    loading,
    refresh,
    hasAdmin: adminConnections.length > 0,
    unreachable,
    unreachableCount,
  };
}

export function outputsSubtitle({
  memberOnly,
  unreachable,
  unreachableCount = 0,
  connectionCount = 0,
  unreadCount = 0,
  hasRows,
}) {
  if (memberOnly) return 'MEMBER';
  if (unreachable && !hasRows && unreachableCount >= connectionCount) return 'UNREACHABLE';
  if (unreachable) return unreadCount > 0 ? `${unreadCount} UNREAD · PARTIAL` : 'PARTIAL';
  return unreadCount > 0 ? `${unreadCount} UNREAD` : 'INBOX ZERO';
}

export function outputsEmptyState({
  memberOnly,
  hasAdmin,
  paired,
  unreachable,
  unreachableCount = 0,
  connectionCount = 0,
}) {
  if (memberOnly) {
    return {
      title: 'Nothing here yet',
      detail: 'The notifications inbox is available to admin connections. This device is paired as a member.',
    };
  }
  if (unreachable) {
    if (connectionCount - unreachableCount > 0) {
      return {
        title: 'Some daemons did not answer',
        detail: `${unreachableCount} of ${connectionCount} daemons did not answer. Anything waiting on them is missing from this list. Pull down to retry.`,
      };
    }
    return {
      title: 'Daemon unreachable',
      detail: 'This phone could not reach your daemon, so notifications waiting there are not shown. Check it is running, then pull down to retry.',
    };
  }
  if (hasAdmin) {
    return {
      title: 'Nothing here yet',
      detail: 'Notifications land here when your agent notifies you or a scheduled job fails.',
    };
  }
  return {
    title: 'Nothing here yet',
    detail: paired
      ? 'Connecting… notifications appear once your daemons respond.'
      : 'Pair this phone to a daemon to see your notifications.',
  };
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
