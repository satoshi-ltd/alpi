import { useEffect, useRef, useState, useSyncExternalStore } from 'react';

export const DONE_MS = 2400;
export const sessionMarkKey = (profile) => (profile ? `profile:${profile}` : null);

export function headerState({ paused = false, offline = false, working = false, needs = false, failed = false, done = false }) {
  if (offline) return 'offline';
  if (paused) return 'paused';
  if (needs) return 'needs';
  if (working) return 'working';
  if (failed) return 'failed';
  if (done) return 'done';
  return 'idle';
}

const marks = new Map();
const listeners = new Set();

function notify() {
  for (const fn of listeners) fn();
}

function attach(key, token, state) {
  let entries = marks.get(key);
  if (!entries) marks.set(key, (entries = new Map()));
  entries.set(token, state);
  notify();
}

function update(key, token, state) {
  const entries = marks.get(key);
  if (!entries?.has(token) || entries.get(token) === state) return;
  entries.set(token, state);
  notify();
}

function detach(key, token) {
  const entries = marks.get(key);
  if (!entries?.delete(token)) return;
  if (entries.size === 0) marks.delete(key);
  notify();
}

function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function sharedSessionMark(key) {
  const entries = key ? marks.get(key) : null;
  return entries?.size ? [...entries.values()].pop() : null;
}

export function useSharedSessionMark(key) {
  return useSyncExternalStore(subscribe, () => sharedSessionMark(key), () => null);
}

export function _resetSessionMarksForTests() {
  marks.clear();
}

const moved = (prev, scope, session) => prev.scope !== scope || (prev.session != null && prev.session !== session);

export function useSessionMark({ key = null, scope = key, session = null, paused = false, offline = false, working = false, needs = false, error = false, cancelled = false }) {
  const [after, setAfter] = useState({ scope, session, value: null });
  const last = useRef({ scope, session, working, error: false, cancelled: false });
  const token = useRef(null);
  if (!token.current) token.current = {};

  useEffect(() => {
    const prev = last.current;
    const started = working && !prev.working;
    const stopped = cancelled || (prev.cancelled && !started && !moved(prev, scope, session));
    last.current = { scope, session, working, error, cancelled: stopped };
    let value;
    if (moved(prev, scope, session) || started) value = null;
    else if (!working && error && (prev.working || !prev.error)) value = 'failed';
    else if (!working && prev.working && !error) value = stopped ? null : 'done';
    setAfter((cur) => {
      const next = value === undefined ? cur.value : value;
      return cur.scope === scope && cur.session === session && cur.value === next ? cur : { scope, session, value: next };
    });
  }, [scope, session, working, error, cancelled]);

  useEffect(() => {
    if (after.value !== 'done') return undefined;
    const timer = setTimeout(() => setAfter((cur) => (cur === after ? { ...cur, value: null } : cur)), DONE_MS);
    return () => clearTimeout(timer);
  }, [after]);

  const value = moved(after, scope, session) ? null : after.value;
  const state = headerState({ paused, offline, working, needs, failed: value === 'failed', done: value === 'done' });
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    if (!key) return undefined;
    const mine = token.current;
    attach(key, mine, stateRef.current);
    return () => detach(key, mine);
  }, [key]);

  useEffect(() => {
    if (key) update(key, token.current, state);
  }, [key, state]);

  return state;
}
