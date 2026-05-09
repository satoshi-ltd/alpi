import { useCallback, useState } from "react";

const PINNED_KEY = "alf:pinned:v1";

function loadPinned() {
  try {
    const raw = localStorage.getItem(PINNED_KEY);
    return raw ? JSON.parse(raw) : { profiles: [], workgroups: [] };
  } catch {
    return { profiles: [], workgroups: [] };
  }
}

export function usePinned() {
  const [pinned, setPinned] = useState(loadPinned);

  const onTogglePin = useCallback((kind, key) => {
    setPinned((prev) => {
      const list = prev[kind] ?? [];
      const next = list.includes(key)
        ? list.filter((k) => k !== key)
        : [...list, key];
      const updated = { ...prev, [kind]: next };
      localStorage.setItem(PINNED_KEY, JSON.stringify(updated));
      return updated;
    });
  }, []);

  return { pinned, onTogglePin };
}
