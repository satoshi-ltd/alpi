// Module-level shared cache so refresh() from any consumer propagates to all subscribers.

import { useCallback, useEffect, useRef, useState } from 'react';

import { useEndpoint } from '../lib/EndpointContext';

const cache = new Map();

function entryFor(key) {
  let entry = cache.get(key);
  if (!entry) {
    entry = { data: null, loading: false, error: null, inflight: null, listeners: new Set() };
    cache.set(key, entry);
  }
  return entry;
}

function snapshotOf(entry) {
  return { data: entry.data, loading: entry.loading, error: entry.error };
}

function notify(entry) {
  const snap = snapshotOf(entry);
  for (const fn of entry.listeners) fn(snap);
}

function keyFor(endpointId, method, params) {
  return `${endpointId ?? '∅'}|${method}|${JSON.stringify(params || {})}`;
}

async function fetchAndStore(key, call, method, params) {
  const entry = entryFor(key);
  if (entry.inflight) return entry.inflight;
  entry.loading = true;
  entry.error = null;
  notify(entry);
  const promise = call(method, params || {})
    .then((result) => {
      entry.data = result;
      entry.loading = false;
      entry.error = null;
      return result;
    })
    .catch((e) => {
      entry.loading = false;
      entry.error = e;
      throw e;
    })
    .finally(() => {
      entry.inflight = null;
      notify(entry);
    });
  entry.inflight = promise;
  return promise;
}

function initialSnapFor(key) {
  if (!key) return { data: null, loading: false, error: null };
  const entry = entryFor(key);
  if (entry.data !== null) return snapshotOf(entry);
  return { data: null, loading: true, error: null };
}

function usePolledCall(method, params, deps, opts = {}) {
  const { endpoint, call } = useEndpoint();
  const skip = !!opts.skipWhen;
  const key = endpoint && !skip ? keyFor(endpoint.id, method, params) : null;

  const [snap, setSnap] = useState(() => initialSnapFor(key));
  // reset snap synchronously on key flip — else one render bleeds prev endpoint's data
  const [trackedKey, setTrackedKey] = useState(key);
  if (trackedKey !== key) {
    setTrackedKey(key);
    setSnap(initialSnapFor(key));
  }

  const keyRef = useRef(key);
  keyRef.current = key;

  useEffect(() => {
    if (!key) return undefined;
    const entry = entryFor(key);
    // captured-key guard: a notify() fired on the prev entry between flip and cleanup must not setSnap with stale data
    const listener = (s) => {
      if (keyRef.current === key) setSnap(s);
    };
    entry.listeners.add(listener);
    setSnap(snapshotOf(entry));
    if (!entry.inflight && entry.data === null) {
      fetchAndStore(key, call, method, params).catch(() => {});
    }
    return () => {
      entry.listeners.delete(listener);
    };
  }, [key, call, method]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useCallback(async () => {
    if (!key) return null;
    try {
      return await fetchAndStore(key, call, method, params);
    } catch {
      return null;
    }
  }, [key, call, method]); // eslint-disable-line react-hooks/exhaustive-deps

  return { ...snap, refresh };
}

export function invalidate(endpointId, method, params = {}) {
  const key = keyFor(endpointId, method, params);
  const entry = cache.get(key);
  if (!entry) return;
  entry.data = null;
  entry.error = null;
  entry.inflight = null;
  notify(entry);
}

export function useProfileSummaries() {
  return usePolledCall('host.profile.summaries', {}, []);
}

// Daemon dedupes by wg_id when called with no profile param.
export function useWorkgroups(profile = null) {
  return usePolledCall('host.workgroups.list', profile ? { profile } : {}, [profile]);
}

export function useProfilesList() {
  return usePolledCall('host.profiles.list', {}, []);
}

// Daemon returns { session: {...} } — unwrap.
export function useSession(profile, sessionId) {
  const inner = usePolledCall(
    'host.session.read',
    profile && sessionId ? { profile, id: sessionId } : null,
    [profile, sessionId],
    { skipWhen: !profile || !sessionId },
  );
  return { ...inner, data: inner.data?.session ?? null };
}

export function useSessionsList(profile, limit = 20) {
  return usePolledCall(
    'host.sessions.list',
    profile ? { profile, limit } : null,
    [profile, limit],
    { skipWhen: !profile },
  );
}

export function useWorkgroupTranscript(profile, wgId) {
  // tail=true + limit=200 keeps first-paint bounded on remote workgroups — a 10k-post hub over Tailscale would otherwise stall the screen for seconds while the full backlog decrypts and ships.
  return usePolledCall(
    'host.workgroup.transcript',
    profile && wgId ? { profile, wg_id: wgId, tail: true, limit: 200 } : null,
    [profile, wgId],
    { skipWhen: !profile || !wgId },
  );
}

export function useWorkgroupMembers(profile, wgId) {
  return usePolledCall(
    'host.workgroup.members',
    profile && wgId ? { profile, wg_id: wgId } : null,
    [profile, wgId],
    { skipWhen: !profile || !wgId },
  );
}

export function useProfileStorage(profile) {
  return usePolledCall('host.profile.storage', { profile }, [profile], { skipWhen: !profile });
}

export function useSkills(profile) {
  return usePolledCall('host.skills.list', { profile }, [profile], { skipWhen: !profile });
}

export function useTools(profile) {
  return usePolledCall('host.tools.list', { profile }, [profile], { skipWhen: !profile });
}

export function useEmailAccounts(profile) {
  return usePolledCall('host.email.status', { profile }, [profile], { skipWhen: !profile });
}

export function useScheduleList(profile) {
  return usePolledCall('host.schedule.list', { profile }, [profile], { skipWhen: !profile });
}

export function useOllamaModels(profile) {
  return usePolledCall('host.providers.ollama_models', { profile }, [profile], { skipWhen: !profile });
}

export function usePeersPending(profile) {
  return usePolledCall('host.peers.pending_list', { profile }, [profile], { skipWhen: !profile });
}

export function useEmailConfig(profile, id) {
  return usePolledCall(
    'host.email.config',
    profile && id ? { profile, id } : null,
    [profile, id],
    { skipWhen: !profile || !id },
  );
}

const MEMORY_FILES = ['USER.md', 'MEMORY.md', 'AGENT.md'];

export function useProfileMemory(profile) {
  const { endpoint, call } = useEndpoint();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const requestIdRef = useRef(0);

  const refresh = useCallback(async () => {
    if (!profile || !endpoint) {
      setData(null);
      setLoading(false);
      return null;
    }
    const id = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.all(
        MEMORY_FILES.map((name) =>
          call('host.profile.read_file', { profile, rel_path: `memories/${name}` })
            .then((r) => ({ name, text: r?.text ?? '' }))
            .catch(() => ({ name, text: '' })),
        ),
      );
      if (id !== requestIdRef.current) return null;
      const map = {};
      for (const r of results) map[r.name] = r.text;
      setData(map);
      setLoading(false);
      return map;
    } catch (e) {
      if (id !== requestIdRef.current) return null;
      setError(e);
      setLoading(false);
      return null;
    }
  }, [profile, endpoint, call]);

  useEffect(() => { refresh(); }, [refresh]);

  return { data, loading, error, refresh };
}
