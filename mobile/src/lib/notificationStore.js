import { useSyncExternalStore } from 'react';

export const UNDO_MS = 5000;

const EMPTY_SET = new Set();
const INITIAL = { trail: null, frozen: null, hidden: EMPTY_SET, unreadMissing: EMPTY_SET };

let state = INITIAL;
const timers = new Map();
const listeners = new Set();

function emit(patch) {
  state = { ...state, ...patch };
  for (const fn of listeners) fn();
}

function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

const snapshot = () => state;

export function useNotificationStore() {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}

export function notificationState() {
  return state;
}

export function setTrail(entries) {
  emit({ trail: Array.isArray(entries) ? entries : null });
}

export function freeze(entry) {
  emit({ frozen: entry ? { key: entry.key, pinned: !!entry.pinned, unread: !!entry.unread } : null });
}

export function trailPosition(key, current = state) {
  const live = (current.trail ?? []).filter((e) => e.key === key || !current.hidden.has(e.key));
  const index = live.findIndex((e) => e.key === key);
  if (index < 0) return null;
  return { index, total: live.length, prev: live[index - 1] ?? null, next: live[index + 1] ?? null };
}

export function withKey(set, key, on) {
  if (set.has(key) === on) return set;
  const next = new Set(set);
  if (on) next.add(key);
  else next.delete(key);
  return next;
}

// A finished delete stays hidden: the row is gone on the daemon, and the list drops it on its next refresh.
export function scheduleDelete(key, run, { delayMs = UNDO_MS, onError } = {}) {
  if (timers.has(key)) clearTimeout(timers.get(key));
  const timer = setTimeout(async () => {
    timers.delete(key);
    try {
      await run();
    } catch (error) {
      emit({ hidden: withKey(state.hidden, key, false) });
      onError?.(error);
    }
  }, delayMs);
  timers.set(key, timer);
  emit({ hidden: withKey(state.hidden, key, true) });
}

export function cancelDelete(key) {
  const timer = timers.get(key);
  if (!timer) return false;
  clearTimeout(timer);
  timers.delete(key);
  emit({ hidden: withKey(state.hidden, key, false) });
  return true;
}

export function noteUnreadMissing(connectionKey) {
  emit({ unreadMissing: withKey(state.unreadMissing, connectionKey, true) });
}

export function _resetNotificationStoreForTests() {
  for (const timer of timers.values()) clearTimeout(timer);
  timers.clear();
  state = INITIAL;
  for (const fn of listeners) fn();
}
