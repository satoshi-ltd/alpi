import { useCallback, useEffect, useRef, useState } from 'react';

import { notificationKey } from '../../../common/notificationTriage.mjs';
import { useEndpoint } from '../lib/EndpointContext';
import { isGone } from '../../../common/isGone.mjs';
import { noteUnreadMissing, scheduleDelete, undoAllDeletes } from '../lib/notificationStore';
import { call as rpcCall } from '../lib/rpc';
import { isMissingVerb } from './useActivity';
import { useDebouncedCallback } from './useDebouncedCallback';
import { useEventEffect } from './useEvents';

const DEFAULT_LIMIT = 100;


export function useOutputs({ profile, status, profiles } = {}) {
  const { endpoint, call } = useEndpoint();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [unreachable, setUnreachable] = useState(false);
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
      setUnreachable(false);
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
            .catch(() => null),
        ),
      );
      if (reqId !== reqRef.current) return;
      const merged = results.filter(Boolean).flat().sort(
        (a, b) => (b.created_at ?? 0) - (a.created_at ?? 0),
      );
      setRows(merged);
      setUnreachable(results.some((r) => !r));
    } finally {
      if (reqId === reqRef.current) setLoading(false);
    }
  }, [endpoint, call, key, status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    refresh();
  }, [refresh]);

  const debouncedRefresh = useDebouncedCallback(refresh, 500);
  useEventEffect(['output.created', 'output.updated'], debouncedRefresh);

  return { rows, loading, refresh, unreachable };
}


// Three modes so an unknown connectionId never silently reads the active daemon — that could open/mark the wrong notification on a profile/id collision.
export function resolveReadTarget(connections, connectionId) {
  if (!connectionId) return { mode: 'active' };
  const connection = (connections ?? []).find((c) => c.id === connectionId);
  return connection ? { mode: 'connection', connection } : { mode: 'unknown' };
}

export function outputCall(connections, call, connectionId, method, params) {
  const target = resolveReadTarget(connections, connectionId);
  if (target.mode === 'unknown') return Promise.reject(new Error(`unknown connection: ${connectionId}`));
  return target.mode === 'connection' ? rpcCall(target.connection, method, params) : call(method, params);
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

  const markUnread = useCallback(async () => {
    if (!profile || !id) return null;
    const res = await outputCall(connections, call, connectionId, 'host.outputs.mark_unread', { profile, id });
    if (res?.output) setRow(res.output);
    return res?.output ?? null;
  }, [call, connections, connectionId, profile, id]);

  const runJob = useCallback(
    (jobId) => outputCall(connections, call, connectionId, 'host.schedule.fire', { profile, id: jobId }),
    [call, connections, connectionId, profile],
  );

  return { row, loading, error, reload: load, markRead, markUnread, runJob };
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


export const unreadMissingKey = (connectionId, activeId) => connectionId || activeId || 'active';

export function useNotificationActions() {
  const { call, connections, activeId } = useEndpoint();
  const send = useCallback(
    (row, method) => outputCall(connections, call, row.connectionId, method, { profile: row.profile, id: row.id }),
    [connections, call],
  );
  const markRead = useCallback((row) => send(row, 'host.outputs.mark_read'), [send]);
  const markUnread = useCallback(async (row) => {
    try {
      await send(row, 'host.outputs.mark_unread');
      return true;
    } catch (e) {
      if (!isMissingVerb(e)) throw e;
      noteUnreadMissing(unreadMissingKey(row.connectionId, activeId));
      return false;
    }
  }, [send, activeId]);
  const remove = useCallback((row, { onError } = {}) => scheduleDelete(notificationKey(row), async () => {
    try {
      await send(row, 'host.outputs.delete');
    } catch (error) {
      if (!isGone(error)) throw error;
    }
  }, { onError }), [send]);
  const undoRemove = useCallback(() => undoAllDeletes(), []);
  return { markRead, markUnread, remove, undoRemove };
}
