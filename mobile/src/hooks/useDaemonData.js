// Module-level shared cache so refresh() from any consumer propagates to all subscribers.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AppState } from 'react-native';

import { defaultAsAlpaca } from '../../../common/folds.mjs';
import { useEndpoint } from '../lib/EndpointContext';
import { useTheme } from '../theme/ThemeContext';
import { quiet } from '../lib/settled';

const cache = new Map();

export function _resetDaemonDataCache() {
  cache.clear();
}

function entryFor(key) {
  let entry = cache.get(key);
  if (!entry) {
    entry = { data: null, loading: false, error: null, inflight: null, trailing: null, updatedAt: 0, listeners: new Set() };
    cache.set(key, entry);
  }
  return entry;
}

function snapshotOf(entry) {
  return {
    data: entry.data,
    loading: entry.loading,
    error: entry.error,
    stale: !!entry.error && entry.data !== null,
    updatedAt: entry.updatedAt,
  };
}

function notify(entry) {
  const snap = snapshotOf(entry);
  for (const fn of entry.listeners) fn(snap);
}

function keyFor(endpointId, method, params) {
  return `${endpointId ?? '∅'}|${method}|${JSON.stringify(params || {})}`;
}

function isAuthFailure(error) {
  const message = String(error?.message || '');
  return (
    (message === 'auth-failed' && error?.data?.reason !== 'connection-disabled') ||
    message === 'forbidden'
  );
}

function isMethodNotFound(error) {
  return error?.code === -32601 || String(error?.message || '').includes('method-not-found');
}

export const RETRY_BASE_MS = 2000;
export const RETRY_MAX_MS = 60000;
export const RETRY_ATTEMPTS = 6;

// Only a lost connection or a refused-for-load socket heals by itself; any answer from the daemon is final.
function isTransient(error) {
  return !!error && (error.transport === true || error.code === -32029);
}

// A plain refresh joins the read in flight; an invalidation (an event) gets one trailing read, since that reply may predate it.
function fetchAndStore(key, call, method, params, { invalidation = false } = {}) {
  const entry = entryFor(key);
  if (entry.inflight) {
    if (!invalidation) return entry.inflight;
    if (!entry.trailing) {
      entry.trailing = entry.inflight.catch(() => {}).then(() => {
        entry.trailing = null;
        if (!entry.listeners.size) return entry.data;
        return startFetch(key, call, method, params);
      });
    }
    return entry.trailing;
  }
  return entry.trailing ?? startFetch(key, call, method, params);
}

function fetchIfIdle(key, call, method, params, minAgeMs = 0) {
  const entry = entryFor(key);
  if (entry.inflight || entry.trailing) return;
  if (entry.error && !isTransient(entry.error)) return;
  if (minAgeMs && entry.updatedAt && Date.now() - entry.updatedAt < minAgeMs) return;
  startFetch(key, call, method, params, { background: true }).catch(() => {});
}

function startFetch(key, call, method, params, { background = false } = {}) {
  const entry = entryFor(key);
  if (entry.inflight) return entry.inflight;
  // A reconcile the user did not ask for must not light the Refreshing indicator every minute.
  if (!background) {
    entry.loading = true;
    notify(entry);
  }
  let request;
  try {
    request = Promise.resolve(call(method, params || {}));
  } catch (e) {
    request = Promise.reject(e);
  }
  const promise = request
    .then((result) => {
      entry.data = result;
      entry.loading = false;
      entry.error = null;
      entry.updatedAt = Date.now();
      return result;
    })
    .catch((e) => {
      entry.loading = false;
      entry.error = e;
      if (isAuthFailure(e)) {
        entry.data = null;
      }
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
  if (!key) return { data: null, loading: false, error: null, stale: false, updatedAt: 0 };
  const entry = entryFor(key);
  if (entry.data !== null) return snapshotOf(entry);
  return { data: null, loading: true, error: null, stale: false, updatedAt: 0 };
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
    if (!entry.inflight) {
      fetchAndStore(key, call, method, params).catch(() => {});
    }
    return () => {
      entry.listeners.delete(listener);
    };
  }, [key, call, method]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useCallback(() => {
    if (!key) return Promise.resolve(null);
    return quiet(fetchAndStore(key, call, method, params));
  }, [key, call, method]); // eslint-disable-line react-hooks/exhaustive-deps

  const invalidateRead = useCallback(() => {
    if (!key) return Promise.resolve(null);
    return quiet(fetchAndStore(key, call, method, params, { invalidation: true }));
  }, [key, call, method]); // eslint-disable-line react-hooks/exhaustive-deps

  useKeptCurrent(key, call, method, params, snap.error, opts.reconcileMs);

  return { ...snap, refresh, invalidate: invalidateRead };
}

// Screens whose tests stub react-native without AppState still render; they just never reconcile.
function appState() {
  try {
    return AppState ?? null;
  } catch {
    return null;
  }
}

function useKeptCurrent(key, call, method, params, error, reconcileMs) {
  const [active, setActive] = useState(() => {
    const state = appState()?.currentState;
    return state !== 'background' && state !== 'inactive';
  });
  const attemptRef = useRef(0);
  const argsRef = useRef({ call, method, params });
  argsRef.current = { call, method, params };

  useEffect(() => {
    const source = appState();
    if (!reconcileMs || !source?.addEventListener) return undefined;
    let previous = source.currentState;
    setActive(previous !== 'background' && previous !== 'inactive');
    const sub = source.addEventListener('change', (state) => {
      const now = state === 'active';
      setActive(now);
      if (now && key) {
        const { call: c, method: m, params: p } = argsRef.current;
        // An inactive blip (Control Center, Face ID, a permission prompt) is not a return from the background.
        fetchIfIdle(key, c, m, p, previous === 'background' ? 0 : reconcileMs / 2);
      }
      previous = state;
    });
    return () => sub?.remove?.();
  }, [key, reconcileMs]);

  useEffect(() => {
    if (!reconcileMs || !key || !active) return undefined;
    const timer = setInterval(() => {
      const { call: c, method: m, params: p } = argsRef.current;
      fetchIfIdle(key, c, m, p, reconcileMs / 2);
    }, reconcileMs);
    return () => clearInterval(timer);
  }, [key, active, reconcileMs]);

  useEffect(() => {
    attemptRef.current = 0;
  }, [key]);

  useEffect(() => {
    if (!error) {
      attemptRef.current = 0;
      return undefined;
    }
    if (!reconcileMs || !key || !active || !isTransient(error) || attemptRef.current >= RETRY_ATTEMPTS) return undefined;
    const delay = Math.min(RETRY_MAX_MS, RETRY_BASE_MS * 2 ** attemptRef.current);
    const timer = setTimeout(() => {
      attemptRef.current += 1;
      const { call: c, method: m, params: p } = argsRef.current;
      fetchIfIdle(key, c, m, p);
    }, delay);
    return () => clearTimeout(timer);
  }, [key, error, active, reconcileMs]);
}

export function seedCache(endpointId, method, params, data) {
  if (!endpointId || data == null) return;
  const entry = entryFor(keyFor(endpointId, method, params));
  entry.data = data;
  entry.error = null;
  notify(entry);
}

export function invalidate(endpointId, method, params = {}) {
  const key = keyFor(endpointId, method, params);
  const entry = cache.get(key);
  if (!entry) return;
  entry.data = null;
  entry.error = null;
  entry.inflight = null;
  entry.trailing = null;
  notify(entry);
}

export const RECONCILE_MS = 60000;

export function useProfileSummaries() {
  const inner = usePolledCall('host.profile.summaries', {}, [], { reconcileMs: RECONCILE_MS });
  const { colors } = useTheme();
  const data = useMemo(() => {
    const profiles = inner.data?.profiles;
    return Array.isArray(profiles) ? { ...inner.data, profiles: profiles.map(defaultAsAlpaca(colors.accent)) } : inner.data;
  }, [inner.data, colors.accent]);
  return { ...inner, data };
}

// storage is excluded on purpose (its os.walk dominates snapshot latency) — needsFallback() fetches it separately; old daemons ignore `sections`.
const SNAPSHOT_SECTIONS = ['detail', 'usage', 'workgroups', 'email', 'schedules'];

export function useProfileSnapshot(profile) {
  const inner = usePolledCall(
    'host.settings.profile_snapshot',
    profile ? { profile, sections: SNAPSHOT_SECTIONS } : null,
    [profile],
    { skipWhen: !profile },
  );
  return {
    ...inner,
    unsupported: isMethodNotFound(inner.error),
  };
}

// Daemon dedupes by wg_id when called with no profile param.
export function useWorkgroups(profile = null) {
  return usePolledCall(
    'host.workgroups.list',
    profile ? { profile, include_pipeline_status: true } : { include_pipeline_status: true },
    [profile],
    { reconcileMs: RECONCILE_MS },
  );
}

export function useProfilesList() {
  return usePolledCall('host.profiles.list', {}, []);
}

export function useSessionsList(profile, limit = 20, opts = {}) {
  return usePolledCall(
    'host.sessions.list',
    profile ? { profile, limit } : null,
    [profile, limit],
    { skipWhen: !profile || !!opts.skipWhen },
  );
}

export function useWorkgroupTranscript(profile, wgId) {
  // tail=true + limit=200 keeps first-paint bounded on remote workgroups — a 10k-post hub over Tailscale would otherwise stall the screen for seconds while the full backlog decrypts and ships.
  return usePolledCall(
    'host.workgroup.transcript',
    profile && wgId ? { profile, wg_id: wgId, tail: true, limit: 200 } : null,
    [profile, wgId],
    { skipWhen: !profile || !wgId, reconcileMs: RECONCILE_MS },
  );
}

// Canonical task + pipeline_run state — the daemon folds it, no client re-derivation.
export function useWorkgroupTasks(profile, wgId) {
  return usePolledCall(
    'host.workgroup.tasks',
    profile && wgId ? { profile, wg_id: wgId } : null,
    [profile, wgId],
    { skipWhen: !profile || !wgId, reconcileMs: RECONCILE_MS },
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

export function useProfileStorage(profile, opts = {}) {
  return usePolledCall(
    'host.profile.storage',
    { profile },
    [profile, opts.skipWhen],
    { skipWhen: !profile || opts.skipWhen },
  );
}

export function useSkills(profile, opts = {}) {
  return usePolledCall(
    'host.skills.list',
    { profile },
    [profile, opts.skipWhen],
    { skipWhen: !profile || opts.skipWhen },
  );
}

export function useTools(profile, opts = {}) {
  return usePolledCall(
    'host.tools.list',
    { profile },
    [profile, opts.skipWhen],
    { skipWhen: !profile || opts.skipWhen },
  );
}

export function useEmailAccounts(profile, opts = {}) {
  return usePolledCall(
    'host.email.status',
    { profile },
    [profile, opts.skipWhen],
    { skipWhen: !profile || opts.skipWhen },
  );
}

export function useScheduleList(profile, opts = {}) {
  return usePolledCall(
    'host.schedule.list',
    { profile },
    [profile, opts.skipWhen],
    { skipWhen: !profile || opts.skipWhen },
  );
}

export function useProfileAttention(profile, opts = {}) {
  const inner = usePolledCall(
    'host.profile.attention',
    { profile },
    [profile, opts.skipWhen],
    { skipWhen: !profile || opts.skipWhen },
  );
  return { ...inner, unsupported: isMethodNotFound(inner.error) };
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
  const scope = endpoint && profile ? `${endpoint.id}|${profile}` : null;
  const [data, setData] = useState(null);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(!!scope);
  const [error, setError] = useState(null);
  const requestIdRef = useRef(0);
  const [trackedScope, setTrackedScope] = useState(scope);
  if (trackedScope !== scope) {
    setTrackedScope(scope);
    setData(null);
    setUsage(null);
    setError(null);
    setLoading(!!scope);
    requestIdRef.current += 1;
  }

  const refresh = useCallback(async () => {
    const id = ++requestIdRef.current;
    if (!profile || !endpoint) {
      setData(null);
      setUsage(null);
      setLoading(false);
      return null;
    }
    setLoading(true);
    setError(null);
    try {
      const [results, usageRes] = await Promise.all([
        Promise.all(
          MEMORY_FILES.map((name) =>
            call('host.profile.read_file', { profile, rel_path: `memories/${name}` })
              .then((r) => ({ name, text: r?.text ?? '' }))
              .catch(() => ({ name, text: '' })),
          ),
        ),
        call('host.profile.memory_usage', { profile }).then((r) => r?.files ?? null).catch(() => null),
      ]);
      if (id !== requestIdRef.current) return null;
      const map = {};
      for (const r of results) map[r.name] = r.text;
      setData(map);
      setUsage(usageRes);
      setLoading(false);
      return map;
    } catch (e) {
      if (id !== requestIdRef.current) return null;
      setError(e);
      setLoading(false);
      return null;
    }
  }, [profile, endpoint, call]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { data, usage, loading, error, refresh };
}

export function useWorkgroupUsage(profile, wgId) {
  return usePolledCall(
    'host.usage.workgroup.daily',
    profile && wgId ? { profile, wg_id: wgId } : null,
    [profile, wgId],
    { skipWhen: !profile || !wgId },
  );
}

export function useConnectionsSummary(opts = {}) {
  return usePolledCall('host.connections.summary', {}, [], { skipWhen: !!opts.skipWhen });
}
