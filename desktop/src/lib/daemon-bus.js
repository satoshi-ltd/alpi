import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "./tauri-listen.js";

// One Tauri listener per event name, fanned out to N subscribers — a reconnect replay (≤200 frames) crosses the bridge once, not once per consumer.
const REINSTALL_RETRY_MS = 2000;

const _buses = new Map();

function bus(name) {
  let b = _buses.get(name);
  if (!b) {
    b = { subs: new Set(), unlisten: null, installing: false, retry: null };
    _buses.set(name, b);
  }
  return b;
}

function ensureInstalled(name) {
  const b = bus(name);
  if (b.unlisten || b.installing) return;
  b.installing = true;
  listen(name, (event) => {
    for (const fn of Array.from(b.subs)) {
      try { fn(event); } catch { /* one subscriber must not starve the rest */ }
    }
  })
    .then((fn) => {
      b.installing = false;
      if (b.subs.size === 0) { safeUnlisten(fn); return; }
      b.unlisten = fn;
    })
    .catch(() => {
      b.installing = false;
      // The bus is the only listener now — re-arm on a delay rather than stranding live subscribers until the next subscribe().
      if (b.subs.size > 0 && !b.retry) {
        b.retry = setTimeout(() => {
          b.retry = null;
          if (b.subs.size > 0) ensureInstalled(name);
        }, REINSTALL_RETRY_MS);
      }
    });
}

export function subscribe(name, handler) {
  const b = bus(name);
  b.subs.add(handler);
  ensureInstalled(name);
  return () => {
    if (!b.subs.delete(handler)) return;
    if (b.subs.size === 0) {
      if (b.retry) { clearTimeout(b.retry); b.retry = null; }
      if (b.unlisten) { safeUnlisten(b.unlisten); b.unlisten = null; }
    }
  };
}

export function subscribeDaemonEvent(handler) {
  return subscribe("daemon-event", handler);
}

export function _resetDaemonBus() {
  for (const b of _buses.values()) {
    if (b.retry) clearTimeout(b.retry);
    safeUnlisten(b.unlisten);
    b.unlisten = null;
    b.subs.clear();
  }
  _buses.clear();
}
