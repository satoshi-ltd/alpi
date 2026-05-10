import { useCallback, useEffect, useState } from "react";

// Pins are scoped per connection — same profile name across connections
// (e.g. "default" on local + remote) must not share state. v2 keys per id;
// v1 was global and is migrated into v2:local on first read for legacy users.
const KEY_PREFIX = "alf:pinned:v2:";
const LEGACY_KEY = "alf:pinned:v1";

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

  useEffect(() => {
    setPinned(load(connectionId));
  }, [connectionId]);

  const onTogglePin = useCallback(
    (kind, key) => {
      setPinned((prev) => {
        const list = prev[kind] ?? [];
        const next = list.includes(key)
          ? list.filter((k) => k !== key)
          : [...list, key];
        const updated = { ...prev, [kind]: next };
        localStorage.setItem(KEY_PREFIX + connectionId, JSON.stringify(updated));
        return updated;
      });
    },
    [connectionId],
  );

  return { pinned, onTogglePin };
}
