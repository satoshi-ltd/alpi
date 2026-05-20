// Pin keys: `p:<name>` (profile) or `wg:<profile>/<id>` (workgroup). Legacy bare profile names migrate to `p:` prefix on load.

import * as SecureStore from 'expo-secure-store';
import { useCallback, useEffect, useState } from 'react';

const KEY = 'alpi.pinned';

function profileKey(name) { return `p:${name}`; }
function workgroupKey(profile, id) { return `wg:${profile}/${id}`; }

async function read() {
  const raw = await SecureStore.getItemAsync(KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((s) => typeof s === 'string')
      .map((s) => (s.includes(':') ? s : profileKey(s)));
  } catch {
    return [];
  }
}

async function write(list) {
  await SecureStore.setItemAsync(KEY, JSON.stringify(list));
}

export function usePins() {
  const [pinned, setPinned] = useState(null);

  useEffect(() => {
    read().then((list) => {
      setPinned(list);
      write(list).catch(() => {});
    }).catch(() => setPinned([]));
  }, []);

  const isProfilePinned = useCallback(
    (name) => Array.isArray(pinned) && pinned.includes(profileKey(name)),
    [pinned],
  );

  const isWorkgroupPinned = useCallback(
    (profile, id) => Array.isArray(pinned) && pinned.includes(workgroupKey(profile, id)),
    [pinned],
  );

  const toggle = useCallback((key) => {
    setPinned((cur) => {
      const list = Array.isArray(cur) ? cur : [];
      const next = list.includes(key) ? list.filter((x) => x !== key) : [...list, key];
      write(next).catch(() => {});
      return next;
    });
  }, []);

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
