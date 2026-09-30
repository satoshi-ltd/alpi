import { useEffect } from "react";

const dirty = new Set();

export function setSettingsDirty(key, value) {
  if (value) dirty.add(key);
  else dirty.delete(key);
}

export function hasDirtySettings() {
  return dirty.size > 0;
}

export function useSettingsDirty(key, value) {
  useEffect(() => {
    setSettingsDirty(key, value);
    return () => setSettingsDirty(key, false);
  }, [key, value]);
}
