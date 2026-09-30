import { useSyncExternalStore } from 'react';
import * as ReactNative from 'react-native';

function accessibility() {
  try {
    return ReactNative.AccessibilityInfo ?? null;
  } catch {
    return null;
  }
}

let value = false;
let started = false;
const listeners = new Set();

function set(next) {
  const flag = !!next;
  if (flag === value) return;
  value = flag;
  for (const fn of listeners) fn();
}

function start() {
  if (started) return;
  started = true;
  const info = accessibility();
  if (!info) return;
  Promise.resolve(info.isReduceMotionEnabled?.()).then(set).catch(() => {});
  info.addEventListener?.('reduceMotionChanged', set);
}

function subscribe(fn) {
  start();
  listeners.add(fn);
  return () => listeners.delete(fn);
}

const snapshot = () => value;

export function useReduceMotion() {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}

export function _resetReduceMotionForTests() {
  value = false;
  started = false;
  listeners.clear();
}
