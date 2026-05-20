// Per-device unread state; daemon is never involved.

import { useCallback, useEffect, useState } from 'react';
import * as SecureStore from 'expo-secure-store';

const STORAGE_KEY = 'alpi.read-state.v1';

let cache = null;
let loaded = false;
const listeners = new Set();

async function ensureLoaded() {
  if (loaded) return cache;
  try {
    const raw = await SecureStore.getItemAsync(STORAGE_KEY);
    cache = raw ? JSON.parse(raw) : {};
  } catch {
    cache = {};
  }
  if (!cache || typeof cache !== 'object') cache = {};
  loaded = true;
  return cache;
}

// Defaults to {} until ensureLoaded resolves — reads during load report "not unread" (safer than spurious dots).
function snapshot() {
  return loaded && cache ? cache : {};
}

function emit() {
  for (const fn of listeners) {
    try { fn(snapshot()); } catch { /* */ }
  }
}

// SecureStore writes hit the native keychain; coalesce bursts to a single trailing write.
let persistTimer = null;
const PERSIST_DEBOUNCE_MS = 250;
function schedulePersist() {
  if (persistTimer) return;
  persistTimer = setTimeout(async () => {
    persistTimer = null;
    try {
      await SecureStore.setItemAsync(STORAGE_KEY, JSON.stringify(cache ?? {}));
    } catch { /* */ }
  }, PERSIST_DEBOUNCE_MS);
}

function setKey(key, ts) {
  if (!key) return;
  const next = ts ?? Math.floor(Date.now() / 1000);
  const prev = snapshot()[key];
  if (prev === next) return;
  cache = { ...snapshot(), [key]: next };
  loaded = true;
  schedulePersist();
  emit();
}

function isUnread(key, latestTs) {
  if (!key || !latestTs) return false;
  return latestTs > (snapshot()[key] ?? 0);
}

const safeConn = (connId) => connId || 'local';
const profileKey = (connId, name) => (name ? `${safeConn(connId)}:profile:${name}` : '');
const workgroupKey = (connId, profile, id) =>
  profile && id ? `${safeConn(connId)}:workgroup:${profile}/${id}` : '';

export function markProfileRead(connId, name, ts) {
  setKey(profileKey(connId, name), ts);
}

export function isProfileUnread(connId, name, sessionUpdatedAt) {
  return isUnread(profileKey(connId, name), sessionUpdatedAt);
}

export function markWorkgroupRead(connId, profile, id, ts) {
  setKey(workgroupKey(connId, profile, id), ts);
}

export function isWorkgroupUnread(connId, profile, id, latestTs) {
  return isUnread(workgroupKey(connId, profile, id), latestTs);
}

// Drop in-memory cache (sign-out path); SecureStore deletion is the caller's job.
export function resetReadState() {
  cache = {};
  loaded = false;
  if (persistTimer) {
    clearTimeout(persistTimer);
    persistTimer = null;
  }
  for (const fn of listeners) {
    try { fn({}); } catch { /* */ }
  }
}

export function useReadState(connId) {
  const [, force] = useState(0);
  useEffect(() => {
    let cancelled = false;
    ensureLoaded().then(() => {
      if (!cancelled) force((n) => n + 1);
    });
    const fn = () => force((n) => n + 1);
    listeners.add(fn);
    return () => {
      cancelled = true;
      listeners.delete(fn);
    };
  }, []);
  const checkProfile = useCallback(
    (name, ts) => isProfileUnread(connId, name, ts),
    [connId],
  );
  const checkWorkgroup = useCallback(
    (profile, id, ts) => isWorkgroupUnread(connId, profile, id, ts),
    [connId],
  );
  return { checkProfile, checkWorkgroup };
}
