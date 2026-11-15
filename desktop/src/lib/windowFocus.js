import { useSyncExternalStore } from "react";

const listeners = new Set();
let focused = true;
let blurSeen = false;

function read() {
  if (typeof document === "undefined") return true;
  if (document.visibilityState === "hidden") return false;
  return !blurSeen || typeof document.hasFocus !== "function" || document.hasFocus();
}

function set(next) {
  if (next === focused) return;
  focused = next;
  for (const fn of listeners) fn();
}

const onFocus = () => set(typeof document === "undefined" || document.visibilityState !== "hidden");
const onBlur = () => {
  blurSeen = true;
  set(false);
};
const onVisibility = () => set(read());

function listen(on) {
  const method = on ? "addEventListener" : "removeEventListener";
  window[method]("focus", onFocus);
  window[method]("blur", onBlur);
  document[method]("visibilitychange", onVisibility);
}

function subscribe(fn) {
  if (typeof window === "undefined") return () => {};
  if (!listeners.size) {
    focused = read();
    listen(true);
  }
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
    if (!listeners.size) listen(false);
  };
}

const snapshot = () => (listeners.size ? focused : read());
const serverSnapshot = () => true;

export function useWindowFocus() {
  return useSyncExternalStore(subscribe, snapshot, serverSnapshot);
}

export function _resetWindowFocus() {
  blurSeen = false;
  focused = true;
}
