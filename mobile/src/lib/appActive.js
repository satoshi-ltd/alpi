import { useSyncExternalStore } from 'react';
import * as ReactNative from 'react-native';

function appState() {
  try {
    return ReactNative.AppState ?? null;
  } catch {
    return null;
  }
}

const listeners = new Set();
let active = true;
let sub = null;

function read() {
  const current = appState()?.currentState;
  return current == null || current === 'active';
}

function set(next) {
  const flag = next == null || next === 'active';
  if (flag === active) return;
  active = flag;
  for (const fn of listeners) fn();
}

function subscribe(fn) {
  if (!listeners.size) {
    active = read();
    sub = appState()?.addEventListener?.('change', set) ?? null;
  }
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
    if (listeners.size) return;
    sub?.remove?.();
    sub = null;
  };
}

const snapshot = () => (listeners.size ? active : read());

export function useAppActive() {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}
