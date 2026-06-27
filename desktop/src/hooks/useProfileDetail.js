import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

// Lazy `host.profile.detail` cache keyed by (connectionId, name) — two daemons with the same profile name must not bleed peers/models/mcps. Invalidate on connection switch via `invalidateProfileDetailCache(prev)`.

function makeKey(connectionId, name) {
  return `${connectionId || "local"}|${name}`;
}

const _cache = new Map();    // key -> detail
const _inflight = new Map(); // key -> Promise<detail>
const _subs = new Set();     // setters notified on cache changes

function notify(key) {
  for (const fn of _subs) {
    try { fn(key); } catch { /* */ }
  }
}

function load(connectionId, name, { force = false } = {}) {
  if (!name) return Promise.resolve(null);
  const key = makeKey(connectionId, name);
  if (!force && _cache.has(key)) return Promise.resolve(_cache.get(key));
  if (_inflight.has(key)) return _inflight.get(key);
  const p = invoke("profile_detail", { profile: name, connectionId })
    .then((d) => {
      _cache.set(key, d || {});
      _inflight.delete(key);
      notify(key);
      return _cache.get(key);
    })
    .catch(() => {
      _inflight.delete(key);
      _cache.set(key, {});
      notify(key);
      return {};
    });
  _inflight.set(key, p);
  return p;
}

let _eventListenerInstalled = false;
const _invalidateTimers = new Map(); // key -> timeout

// Per-key leading-edge coalesce: a reconnect backfill can replay dozens of config_changed frames per profile — one force-refetch 300ms later covers them all.
function scheduleInvalidate(connectionId, profile) {
  const key = makeKey(connectionId, profile);
  if (_invalidateTimers.has(key)) return;
  _invalidateTimers.set(key, setTimeout(() => {
    _invalidateTimers.delete(key);
    _cache.delete(key);
    load(connectionId, profile, { force: true });
  }, 300));
}

function ensureEventListener() {
  if (_eventListenerInstalled) return;
  _eventListenerInstalled = true;
  // Refetch on daemon-side mutations for the specific (connection, profile).
  listen("daemon-event", (event) => {
    const payload = event.payload ?? {};
    const frame = payload.frame ?? payload;
    const kind = frame?.event;
    const profile = frame?.data?.profile;
    const connectionId = payload.connection_id;
    if (!profile || !connectionId) return;
    if (
      kind === "config_changed"
      || kind === "email_changed"
      || kind === "peers_changed"
    ) {
      scheduleInvalidate(connectionId, profile);
    }
  }).catch(() => {
    // Re-arm on the next hook mount — a swallowed install failure would silently serve stale details forever.
    _eventListenerInstalled = false;
  });
}

// `connectionId` and `name` may be null/undefined — the hook stays idle.
export function useProfileDetail(connectionId, name, { refreshOnMount = false } = {}) {
  ensureEventListener();
  const [, setTick] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!name) return undefined;
    let cancelled = false;
    setLoading(true);
    load(connectionId, name, { force: refreshOnMount }).then(() => {
      if (!cancelled) setTick((t) => t + 1);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    const key = makeKey(connectionId, name);
    const fn = (changed) => {
      if (changed === key) setTick((t) => t + 1);
    };
    _subs.add(fn);
    return () => {
      cancelled = true;
      _subs.delete(fn);
    };
  }, [connectionId, name, refreshOnMount]);

  const refresh = useCallback(() => {
    if (!name) return Promise.resolve(null);
    setLoading(true);
    return load(connectionId, name, { force: true })
      .finally(() => setLoading(false));
  }, [connectionId, name]);

  const detail = name ? (_cache.get(makeKey(connectionId, name)) ?? null) : null;
  return { detail, loading, refresh };
}

export function invalidateProfileDetailCache(connectionId) {
  // Drop every key tied to this connection so a daemon switch never surfaces another host's detail.
  const prefix = `${connectionId || "local"}|`;
  for (const k of Array.from(_cache.keys())) {
    if (k.startsWith(prefix)) _cache.delete(k);
  }
  for (const k of Array.from(_inflight.keys())) {
    if (k.startsWith(prefix)) _inflight.delete(k);
  }
}

// Test-only.
export function _clearProfileDetailCache() {
  _cache.clear();
  _inflight.clear();
  for (const t of _invalidateTimers.values()) clearTimeout(t);
  _invalidateTimers.clear();
  _eventListenerInstalled = false;
}
