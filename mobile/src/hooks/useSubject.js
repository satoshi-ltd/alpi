// Small derived hooks so screens can grab a single profile / workgroup from the cached lists without re-fetching.

import { useEffect, useMemo, useState } from 'react';

import { useEndpoint } from '../lib/EndpointContext';
import { useEventEffect } from './useEvents';
import { useProfileSummaries, useWorkgroups } from './useDaemonData';

export function useProfile(name) {
  const summaries = useProfileSummaries();
  const { call } = useEndpoint();
  const [detail, setDetail] = useState(null);
  const summary = useMemo(
    () => summaries.data?.profiles?.find((p) => p.name === name) ?? null,
    [summaries.data, name],
  );

  // host.profile.summaries is the hot path (inbox poll) — it intentionally omits peers / models / mcps / provider_keys / sandbox / voice. Settings screens need those, so fetch the heavy companion once per profile screen and refresh only when config/peers/gateway events fire for this profile.
  useEffect(() => {
    if (!name) return undefined;
    let cancelled = false;
    call('host.profile.detail', { profile: name })
      .then((d) => { if (!cancelled) setDetail(d || null); })
      .catch(() => { if (!cancelled) setDetail(null); });
    return () => { cancelled = true; };
  }, [name, call]);

  useEventEffect(['config_changed', 'gateway_changed', 'peers_changed'], (ev) => {
    if (!name) return;  // global events shouldn't fire a host.profile.detail("") roundtrip
    if (ev?.data?.profile && ev.data.profile !== name) return;
    call('host.profile.detail', { profile: name })
      .then((d) => setDetail(d || null))
      .catch(() => { /* */ });
  });

  const profile = useMemo(
    () => (summary ? { ...summary, ...(detail || {}) } : null),
    [summary, detail],
  );
  return { profile, loading: summaries.loading, error: summaries.error, refresh: summaries.refresh };
}

export function useWorkgroup(id) {
  const wgs = useWorkgroups();
  const workgroup = useMemo(
    () => wgs.data?.workgroups?.find((w) => w.id === id) ?? null,
    [wgs.data, id],
  );
  return { workgroup, loading: wgs.loading, error: wgs.error, refresh: wgs.refresh };
}
