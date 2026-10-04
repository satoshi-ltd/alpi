import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as ReactNative from 'react-native';

import { useEndpoint } from '../lib/EndpointContext';
import { STREAM_CONNECTED } from '../lib/streamEvents';
import { useDebouncedCallback } from './useDebouncedCallback';
import { useEventEffect } from './useEvents';

export const ACTIVITY_METHOD = 'host.activity.list';
export const ACTIVITY_DEBOUNCE_MS = 300;
export const FAILED_WINDOW_S = 24 * 3600;

export const EMPTY_ACTIVITY = Object.freeze({ needsYou: [], running: [], scheduled: [] });

const list = (value) => (Array.isArray(value) ? value.filter((row) => row && typeof row === 'object') : []);

export function normalizeActivity(raw) {
  if (!raw || typeof raw !== 'object') return EMPTY_ACTIVITY;
  return {
    needsYou: list(raw.needs_you),
    running: list(raw.running),
    scheduled: list(raw.scheduled),
  };
}

export function isMissingVerb(error) {
  if (error?.code === -32601) return true;
  const message = String(error?.message ?? '').toLowerCase();
  if (message === 'forbidden') return true;
  return message.includes('method-not-found') || message.includes('method_not_found') || message.includes('unknown method');
}

export function toEpochSeconds(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value > 1e12 ? value / 1000 : value;
  if (typeof value === 'string' && value.trim()) {
    const asNumber = Number(value);
    if (Number.isFinite(asNumber)) return toEpochSeconds(asNumber);
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed / 1000 : null;
  }
  return null;
}

export function recentlyFailed(job, nowSec) {
  if (job?.last_run_status !== 'error') return false;
  const at = toEpochSeconds(job.last_run_at);
  return at === null || nowSec - at <= FAILED_WINDOW_S;
}

export const profileKey = (name) => `profile:${name}`;
export const workgroupKey = (id) => `workgroup:${id}`;

const RANK = { 'needs-you': 3, failed: 2, working: 1 };

function raise(map, key, next) {
  const prev = map.get(key);
  if (!prev || RANK[next.state] > RANK[prev.state]) map.set(key, { ...prev, ...next });
  else if (next.phases && !prev.phases) map.set(key, { ...prev, phases: next.phases });
}

export function rowStates(activity, nowSec = Date.now() / 1000) {
  const map = new Map();
  const rerunning = new Set((activity?.running ?? []).filter((run) => run.job_id).map((run) => `${run.profile}/${run.job_id}`));
  for (const item of activity?.needsYou ?? []) {
    if (item.profile) raise(map, profileKey(item.profile), { state: 'needs-you' });
  }
  for (const job of activity?.scheduled ?? []) {
    if (job.profile && recentlyFailed(job, nowSec) && !rerunning.has(`${job.profile}/${job.job_id}`)) {
      raise(map, profileKey(job.profile), { state: 'failed' });
    }
  }
  for (const run of activity?.running ?? []) {
    if (run.kind === 'workgroup' && run.workgroup_id) {
      const total = Number(run.phases_total);
      const done = Number(run.phases_done);
      const phases = Number.isFinite(total) && total > 0 && Number.isFinite(done) ? `${done}/${total}` : null;
      raise(map, workgroupKey(run.workgroup_id), { state: 'working', phases });
    } else if (run.profile) {
      raise(map, profileKey(run.profile), { state: 'working' });
    }
  }
  return map;
}

export function rowStateFor(states, item) {
  if (!states || !item?.id) return null;
  return states.get(item.kind === 'workgroup' ? workgroupKey(item.id) : profileKey(item.id)) ?? null;
}

function appState() {
  try {
    return ReactNative.AppState ?? null;
  } catch {
    return null;
  }
}

const stores = new Map();

function storeFor(id) {
  let store = stores.get(id);
  if (!store) {
    store = { data: null, supported: true, inflight: null, listeners: new Set() };
    stores.set(id, store);
  }
  return store;
}

function publish(store) {
  for (const fn of store.listeners) fn();
}

function fetchInto(store, call) {
  if (store.inflight) return store.inflight;
  store.inflight = Promise.resolve()
    .then(() => call(ACTIVITY_METHOD, {}))
    .then((res) => {
      store.data = normalizeActivity(res);
      store.supported = true;
    })
    .catch((error) => {
      if (isMissingVerb(error)) {
        store.supported = false;
        store.data = null;
      }
    })
    .finally(() => {
      store.inflight = null;
      publish(store);
    });
  return store.inflight;
}

export function _resetActivityForTests() {
  stores.clear();
}

export function useActivity() {
  const { endpoint, call } = useEndpoint();
  const id = endpoint?.id ?? null;
  const callRef = useRef(call);
  callRef.current = call;
  const [, bump] = useState(0);

  useEffect(() => {
    if (!id) return undefined;
    const store = storeFor(id);
    const listener = () => bump((n) => n + 1);
    store.listeners.add(listener);
    fetchInto(store, (...args) => callRef.current(...args));
    return () => {
      store.listeners.delete(listener);
    };
  }, [id]);

  const refreshIfSupported = useCallback(() => {
    if (!id) return Promise.resolve();
    const store = storeFor(id);
    if (!store.supported) return Promise.resolve();
    return fetchInto(store, (...args) => callRef.current(...args));
  }, [id]);

  const refresh = useCallback(() => {
    if (!id) return Promise.resolve();
    return fetchInto(storeFor(id), (...args) => callRef.current(...args));
  }, [id]);

  useEffect(() => {
    const sub = appState()?.addEventListener?.('change', (state) => {
      if (state === 'active') refresh();
    });
    return () => sub?.remove?.();
  }, [refresh]);

  const debounced = useDebouncedCallback(refreshIfSupported, ACTIVITY_DEBOUNCE_MS);
  useEventEffect(['activity.changed'], debounced);
  useEventEffect([STREAM_CONNECTED], () => {
    if (id && !storeFor(id).supported) refresh();
  });

  const store = id ? storeFor(id) : null;
  const supported = !!store?.supported && !!store?.data;
  const activity = supported ? store.data : EMPTY_ACTIVITY;
  const states = useMemo(() => rowStates(activity), [activity]);

  return {
    supported,
    unsupported: store?.supported === false,
    activity,
    states,
    needsYouCount: activity.needsYou.length,
    refresh,
  };
}
