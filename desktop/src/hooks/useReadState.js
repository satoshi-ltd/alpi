import { useCallback, useEffect, useState } from "react";

// Frontend-only read-state: localStorage keyed by `<connId>:profile:<name>`; compare against latest_session.updated_at to decide unread.

const STORAGE_KEY = "alpi:read-state:v1";
const listeners = new Set();
let cache = null;

function load() {
  if (cache !== null) return cache;
  try {
    cache = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}") || {};
  } catch {
    cache = {};
  }
  return cache;
}

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cache));
  } catch {
    // Quota / private-mode → drop silently; rows just stay unread instead of crashing.
  }
}

function emit() {
  for (const fn of listeners) fn(cache);
}

function setKey(key, ts) {
  if (!key) return;
  const next = ts ?? Math.floor(Date.now() / 1000);
  cache = { ...load(), [key]: next };
  persist();
  emit();
}

function isUnread(key, latestTs) {
  if (!key || !latestTs) return false;
  return latestTs > (load()[key] ?? 0);
}

const safeConn = (connId) => connId || "local";
const profileKey = (connId, name) =>
  name ? `${safeConn(connId)}:profile:${name}` : "";

export function markProfileRead(connId, name, ts) {
  setKey(profileKey(connId, name), ts);
}

export function isProfileUnread(connId, name, sessionUpdatedAt) {
  return isUnread(profileKey(connId, name), sessionUpdatedAt);
}

export function purgeConnectionReadState(connId) {
  if (!connId || connId === "local") return;
  const prefix = `${connId}:`;
  const current = load();
  const next = {};
  let changed = false;
  for (const [key, value] of Object.entries(current)) {
    if (key.startsWith(prefix)) changed = true;
    else next[key] = value;
  }
  if (!changed) return;
  cache = next;
  persist();
  emit();
}

export function useReadState(connId) {
  const [, force] = useState(0);
  useEffect(() => {
    const fn = () => force((n) => n + 1);
    listeners.add(fn);
    return () => listeners.delete(fn);
  }, []);
  const checkProfile = useCallback(
    (name, ts) => isProfileUnread(connId, name, ts),
    [connId],
  );
  return { checkProfile };
}
