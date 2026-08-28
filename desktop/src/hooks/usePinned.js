import { useCallback, useEffect, useRef, useState } from "react";

// Pins are scoped per connection — same profile name across connections
// (e.g. "default" on local + remote) must not share state. v2 keys per id;
// v1 was global and is migrated into v2:local on first read for legacy users.
const KEY_PREFIX = "alf:pinned:v2:";
const LEGACY_KEY = "alf:pinned:v1";
const TRANSIENT_CACHE_PREFIXES = [
  "alpi.session.cache.v1.",
  "alpi.workgroup.cache.",
];

function persist(connectionId, pinned) {
  const storageKey = KEY_PREFIX + connectionId;
  const serialized = JSON.stringify(pinned);
  try {
    localStorage.setItem(storageKey, serialized);
    return;
  } catch (error) {
    if (error?.name !== "QuotaExceededError") return;
  }

  try {
    const disposable = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (key && TRANSIENT_CACHE_PREFIXES.some((prefix) => key.startsWith(prefix))) {
        disposable.push(key);
      }
    }
    for (const key of disposable) localStorage.removeItem(key);
    localStorage.setItem(storageKey, serialized);
  } catch {}
}

function load(connectionId) {
  try {
    const raw = localStorage.getItem(KEY_PREFIX + connectionId);
    if (raw) return JSON.parse(raw);
    if (connectionId === "local") {
      const legacy = localStorage.getItem(LEGACY_KEY);
      if (legacy) {
        localStorage.setItem(KEY_PREFIX + "local", legacy);
        localStorage.removeItem(LEGACY_KEY);
        return JSON.parse(legacy);
      }
    }
  } catch {}
  return { profiles: [], workgroups: [] };
}

export function usePinned(connectionId = "local") {
  const [pinned, setPinned] = useState(() => load(connectionId));
  const pinnedRef = useRef(pinned);

  useEffect(() => {
    const next = load(connectionId);
    pinnedRef.current = next;
    setPinned(next);
  }, [connectionId]);

  const onTogglePin = useCallback(
    (kind, key) => {
      const previous = pinnedRef.current;
      const list = previous[kind] ?? [];
      const next = list.includes(key)
        ? list.filter((item) => item !== key)
        : [...list, key];
      const updated = { ...previous, [kind]: next };
      pinnedRef.current = updated;
      setPinned(updated);
      persist(connectionId, updated);
    },
    [connectionId],
  );

  return { pinned, onTogglePin };
}
