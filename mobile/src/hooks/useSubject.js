// Small derived hooks so screens can grab a single profile / workgroup from the cached lists without re-fetching.

import { useCallback, useEffect, useMemo, useState } from 'react';

import { useEndpoint } from '../lib/EndpointContext';
import { useDebouncedCallback } from './useDebouncedCallback';
import { useEventEffect } from './useEvents';
import { releaseLandedRead, useProfileSummaries, useWorkgroups } from './useDaemonData';
import { editClock } from '../lib/optimisticProfiles';

export function useProfile(name, opts = {}) {
  const summaries = useProfileSummaries();
  const { call, endpoint } = useEndpoint();
  const endpointId = endpoint?.id ?? null;
  const readDetail = useCallback(() => {
    const params = { profile: name };
    const since = editClock();
    return call('host.profile.detail', params).then((d) => {
      releaseLandedRead(endpointId, 'host.profile.detail', params, d, since);
      return d;
    });
  }, [call, name, endpointId]);
  const [detail, setDetail] = useState(null);
  // reset detail synchronously on name/endpoint flip — else prev endpoint's detail bleeds for one frame
  const [tracked, setTracked] = useState({ name, call });
  if (tracked.name !== name || tracked.call !== call) {
    setTracked({ name, call });
    setDetail(null);
  }
  const summary = useMemo(
    () => summaries.data?.profiles?.find((p) => p.name === name) ?? null,
    [summaries.data, name],
  );

  useEffect(() => {
    if (opts.skipDetail) return undefined;
    if (!name) return undefined;
    let cancelled = false;
    const params = { profile: name };
    const since = editClock();
    call('host.profile.detail', params)
      .then((d) => {
        if (cancelled) return;
        releaseLandedRead(endpointId, 'host.profile.detail', params, d, since);
        setDetail(d || null);
      })
      .catch(() => { if (!cancelled) setDetail(null); });
    return () => { cancelled = true; };
  }, [name, call, endpointId, opts.skipDetail]);

  const refetchDetail = useDebouncedCallback(() => {
    if (!name) return;
    readDetail()
      .then((d) => setDetail(d || null))
      .catch(() => { /* */ });
  }, 300);
  useEventEffect(['config_changed', 'email_changed', 'peers_changed'], (ev) => {
    if (!name) return;  // global events shouldn't fire a host.profile.detail("") roundtrip
    if (ev?.data?.profile && ev.data.profile !== name) return;
    refetchDetail();
  });

  const profile = useMemo(
    () => (summary ? { ...summary, ...(detail || {}) } : null),
    [summary, detail],
  );
  const refreshDetail = useCallback(async () => {
    if (!name) return;
    if (opts.skipDetail) return;
    try {
      const d = await readDetail();
      setDetail(d || null);
    } catch {
      // keep stale snapshot on failure — never blank a populated UI.
    }
  }, [name, readDetail, opts.skipDetail]);
  return {
    profile,
    loading: summaries.loading,
    error: summaries.error,
    refresh: summaries.refresh,
    invalidate: summaries.invalidate,
    refreshDetail,
  };
}

export function useWorkgroup(id) {
  const wgs = useWorkgroups();
  const workgroup = useMemo(
    () => wgs.data?.workgroups?.find((w) => w.id === id) ?? null,
    [wgs.data, id],
  );
  return { workgroup, loading: wgs.loading, error: wgs.error, refresh: wgs.refresh };
}
