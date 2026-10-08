import { useSyncExternalStore } from 'react';

import { createUndoBatch, UNDO_WINDOW_MS } from '../../../common/undoBatch.mjs';

export const UNDO_MS = UNDO_WINDOW_MS;

const EMPTY_SET = new Set();
const INITIAL = { trail: null, frozen: null, hidden: EMPTY_SET, unreadMissing: EMPTY_SET };

let state = INITIAL;
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
const deletes = createUndoBatch({
  commit: (batch) => {
    for (const entry of batch) {
      Promise.resolve()
        .then(entry.run)
        .catch((error) => {
          emit({ hidden: withKey(state.hidden, entry.key, false) });
          entry.onError?.(error);
        });
    }
  },
});

export function scheduleDelete(key, run, { delayMs, onError } = {}) {
  const count = deletes.add(key, { key, run, onError }, { delayMs });
  emit({ hidden: withKey(state.hidden, key, true) });
  return count;
}

export function undoAllDeletes() {
  let hidden = state.hidden;
  for (const entry of deletes.undoAll()) hidden = withKey(hidden, entry.key, false);
  if (hidden === state.hidden) return false;
  emit({ hidden });
  return true;
}

export function noteUnreadMissing(connectionKey) {
  emit({ unreadMissing: withKey(state.unreadMissing, connectionKey, true) });
}

export function _resetNotificationStoreForTests() {
  deletes.undoAll();
  state = INITIAL;
  for (const fn of listeners) fn();
}
