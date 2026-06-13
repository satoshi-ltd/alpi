import { useCallback, useEffect, useRef, useState } from 'react';

import { useEndpoint } from '../lib/EndpointContext';
import { call as rpcCall } from '../lib/rpc';
import { useDebouncedCallback } from './useDebouncedCallback';
import { useEventEffect } from './useEvents';

const DEFAULT_LIMIT = 100;

export function useOutputs({ profile, status, profiles } = {}) {
  const { endpoint, call } = useEndpoint();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const reqRef = useRef(0);

  const profileList = profile
    ? [profile]
    : Array.isArray(profiles) && profiles.length > 0
      ? profiles
      : ['default'];
  const key = profileList.join(',');

  const refresh = useCallback(async () => {
    if (!endpoint) {
      setRows([]);
      return;
    }
    const reqId = ++reqRef.current;
    setLoading(true);
    try {
      const results = await Promise.all(
        profileList.map((p) =>
          call('host.outputs.list', {
            profile: p,
            ...(status ? { status } : {}),
            limit: DEFAULT_LIMIT,
          })
            .then((res) => (res?.outputs ?? []).map((o) => ({ ...o, profile: o.profile || p })))
            .catch(() => []),
        ),
      );
      if (reqId !== reqRef.current) return;
      const merged = results.flat().sort(
        (a, b) => (b.created_at ?? 0) - (a.created_at ?? 0),
      );
      setRows(merged);
    } finally {
      if (reqId === reqRef.current) setLoading(false);
    }
  }, [endpoint, call, key, status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    refresh();
  }, [refresh]);

  const debouncedRefresh = useDebouncedCallback(refresh, 500);
  useEventEffect(['output.created', 'output.updated'], debouncedRefresh);

  return { rows, loading, refresh };
}


// Three modes so an unknown connectionId never silently reads the active daemon — that could open/mark the wrong notification on a profile/id collision.
export function resolveReadTarget(connections, connectionId) {
  if (!connectionId) return { mode: 'active' };
  const connection = (connections ?? []).find((c) => c.id === connectionId);
  return connection ? { mode: 'connection', connection } : { mode: 'unknown' };
}

export function useOutput(profile, id, connectionId) {
  const { endpoint, call, connections } = useEndpoint();
  const [row, setRow] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!profile || !id) return;
    const target = resolveReadTarget(connections, connectionId);
    if (target.mode === 'unknown') {
      setRow(null);
      setError(new Error(`unknown connection: ${connectionId}`));
      setLoading(false);
      return;
    }
    if (target.mode === 'active' && !endpoint) return;
    setLoading(true);
    setError(null);
    try {
      const res = target.mode === 'connection'
        ? await rpcCall(target.connection, 'host.outputs.read', { profile, id })
        : await call('host.outputs.read', { profile, id });
      setRow(res?.output ?? null);
    } catch (e) {
      setError(e);
      setRow(null);
    } finally {
      setLoading(false);
    }
  }, [endpoint, call, connections, connectionId, profile, id]);

  useEffect(() => {
    load();
  }, [load]);

  const markRead = useCallback(async () => {
    if (!profile || !id) return;
    const target = resolveReadTarget(connections, connectionId);
    if (target.mode === 'unknown') return;
    if (target.mode === 'active' && !endpoint) return;
    try {
      const res = target.mode === 'connection'
        ? await rpcCall(target.connection, 'host.outputs.mark_read', { profile, id })
        : await call('host.outputs.mark_read', { profile, id });
      if (res?.output) setRow(res.output);
    } catch {
      /* */
    }
  }, [endpoint, call, connections, connectionId, profile, id]);

  return { row, loading, error, reload: load, markRead };
}


export function useMarkAllOutputsRead() {
  const { endpoint, call } = useEndpoint();
  return useCallback(async (profile) => {
    if (!endpoint || !profile) return 0;
    try {
      const res = await call('host.outputs.mark_all_read', { profile });
      return res?.count ?? 0;
    } catch {
      return 0;
    }
  }, [endpoint, call]);
}
