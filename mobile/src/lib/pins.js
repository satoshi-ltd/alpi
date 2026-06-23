import * as SecureStore from 'expo-secure-store';
import { useCallback, useEffect, useState } from 'react';

const KEY_PREFIX = 'alpi.pinned.';
const LEGACY_KEY = 'alpi.pinned';

function profileKey(name) { return `p:${name}`; }
function workgroupKey(profile, id) { return `wg:${profile}/${id}`; }

function normalize(parsed) {
  if (!Array.isArray(parsed)) return [];
  return parsed
    .filter((s) => typeof s === 'string')
    .map((s) => (s.includes(':') ? s : profileKey(s)));
}

async function read(connectionId) {
  const key = KEY_PREFIX + connectionId;
  let raw = await SecureStore.getItemAsync(key);
  if (!raw) {
    const legacy = await SecureStore.getItemAsync(LEGACY_KEY);
    if (legacy) {
      await SecureStore.setItemAsync(key, legacy);
      await SecureStore.deleteItemAsync(LEGACY_KEY);
      raw = legacy;
    }
  }
  if (!raw) return [];
  try {
    return normalize(JSON.parse(raw));
  } catch {
    return [];
  }
}

async function write(connectionId, list) {
  await SecureStore.setItemAsync(KEY_PREFIX + connectionId, JSON.stringify(list));
}

export function usePins(connectionId) {
  const [pinned, setPinned] = useState(null);

  useEffect(() => {
    if (!connectionId) {
      setPinned([]);
      return undefined;
    }
    let alive = true;
    setPinned(null);
    read(connectionId)
      .then((list) => {
        if (!alive) return;
        setPinned(list);
        write(connectionId, list).catch(() => {});
      })
      .catch(() => { if (alive) setPinned([]); });
    return () => { alive = false; };
  }, [connectionId]);

  const isProfilePinned = useCallback(
    (name) => Array.isArray(pinned) && pinned.includes(profileKey(name)),
    [pinned],
  );

  const isWorkgroupPinned = useCallback(
    (profile, id) => Array.isArray(pinned) && pinned.includes(workgroupKey(profile, id)),
    [pinned],
  );

  const toggle = useCallback((key) => {
    if (!connectionId) return;
    setPinned((cur) => {
      const list = Array.isArray(cur) ? cur : [];
      const next = list.includes(key) ? list.filter((x) => x !== key) : [...list, key];
      write(connectionId, next).catch(() => {});
      return next;
    });
  }, [connectionId]);

  const toggleProfile = useCallback((name) => toggle(profileKey(name)), [toggle]);
  const toggleWorkgroup = useCallback(
    (profile, id) => toggle(workgroupKey(profile, id)),
    [toggle],
  );

  return {
    pinned: pinned ?? [],
    ready: pinned !== null,
    isProfilePinned,
    isWorkgroupPinned,
    toggleProfile,
    toggleWorkgroup,
  };
}
