import { subscribeDaemonEvent } from "./daemon-bus.js";

// Keys MUST be `${connectionId || "local"}|…` — invalidateConnectionCaches relies on that prefix.

const _registry = new Set();

export function createSwrCache({ fetcher, events = null, coalesceMs = 300 }) {
  const entries = new Map();
  const timers = new Map();
  let unsubEvents = null;

  function entryFor(key) {
    let entry = entries.get(key);
    if (!entry) {
      entry = { value: undefined, error: null, gen: 0, inflight: null, params: null, listeners: new Set() };
      entries.set(key, entry);
    }
    return entry;
  }

  function notify(entry) {
    for (const fn of Array.from(entry.listeners)) {
      try { fn(); } catch {}
    }
  }

  function ensureEvents() {
    if (!events || unsubEvents) return;
    unsubEvents = subscribeDaemonEvent((event) => {
      const payload = event?.payload ?? {};
      const frame = payload.frame ?? payload;
      if (!events.kinds.has(frame?.event)) return;
      for (const [key, entry] of Array.from(entries)) {
        if (!events.match(key, frame, payload)) continue;
        if (entry.listeners.size === 0) {
          // Nobody watching: drop instead of refetching — the next mount revalidates anyway.
          entries.delete(key);
          continue;
        }
        if (timers.has(key)) continue;
        timers.set(key, setTimeout(() => {
          timers.delete(key);
          load(key, entry.params, { force: true });
        }, coalesceMs));
      }
    });
  }

  function load(key, params, { force = false } = {}) {
    const entry = entryFor(key);
    if (params !== undefined) entry.params = params;
    if (!force && entry.inflight) return entry.inflight;
    const gen = ++entry.gen;
    let fetched;
    // The fetcher must fire synchronously — tests (and loading probes) observe the RPC in the same tick as the effect.
    try {
      fetched = Promise.resolve(fetcher(entry.params));
    } catch (e) {
      fetched = Promise.reject(e);
    }
    const p = fetched
      .then((value) => {
        if (entry.gen === gen) {
          entry.value = value;
          entry.error = null;
        }
        return entries.get(key)?.value;
      })
      .catch((e) => {
        if (entry.gen === gen) {
          entry.error = e;
          const message = String(e);
          if (message.includes("auth-failed") && !message.includes("connection-disabled")) {
            entry.value = undefined;
          }
        }
        return entries.get(key)?.value;
      })
      .finally(() => {
        if (entry.inflight === p) entry.inflight = null;
        notify(entry);
      });
    entry.inflight = p;
    return p;
  }

  function get(key) {
    return entries.get(key)?.value;
  }

  function errorOf(key) {
    return entries.get(key)?.error ?? null;
  }

  function seed(key, value) {
    const entry = entryFor(key);
    entry.gen += 1;
    entry.value = value;
    entry.error = null;
    notify(entry);
  }

  function subscribe(key, fn) {
    ensureEvents();
    const entry = entryFor(key);
    entry.listeners.add(fn);
    return () => entry.listeners.delete(fn);
  }

  function invalidateConnection(connectionId) {
    const prefix = `${connectionId || "local"}|`;
    for (const key of Array.from(entries.keys())) {
      if (key.startsWith(prefix)) entries.delete(key);
    }
  }

  function clear() {
    entries.clear();
    for (const t of timers.values()) clearTimeout(t);
    timers.clear();
    if (unsubEvents) {
      unsubEvents();
      unsubEvents = null;
    }
  }

  const cache = { load, get, errorOf, seed, subscribe, invalidateConnection, clear };
  _registry.add(cache);
  return cache;
}

export function invalidateConnectionCaches(connectionId) {
  for (const cache of _registry) cache.invalidateConnection(connectionId);
}

// Test-only.
export function _clearAllSwrCaches() {
  for (const cache of _registry) cache.clear();
}
