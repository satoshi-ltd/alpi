import { useCallback, useEffect, useState } from "react";

// Frontend-only read-state: localStorage keyed by `<connId>:profile:<name>` / `<connId>:workgroup:<profile>/<id>`; compare against latest_session.updated_at / workgroup.mtime to decide unread.

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
const workgroupKey = (connId, profile, id) =>
  profile && id ? `${safeConn(connId)}:workgroup:${profile}/${id}` : "";

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
  const checkWorkgroup = useCallback(
    (profile, id, ts) => isWorkgroupUnread(connId, profile, id, ts),
    [connId],
  );
  return { checkProfile, checkWorkgroup };
}
