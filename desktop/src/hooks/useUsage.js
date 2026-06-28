import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

const WEEKDAY_INITIALS = ["S", "M", "T", "W", "T", "F", "S"];
const _cache = new Map();

export function toUsageDays(rpcDays) {
  if (!Array.isArray(rpcDays)) return [];
  return rpcDays.map((d, i) => {
    const dt = new Date(`${d.iso}T00:00:00`);
    return {
      iso: d.iso,
      label: WEEKDAY_INITIALS[dt.getDay()] ?? "",
      day: `${dt.getMonth() + 1}/${dt.getDate()}`,
      tokIn: d.tokIn || 0,
      tokOut: d.tokOut || 0,
      cost: d.cost || 0,
      today: i === rpcDays.length - 1,
    };
  });
}

function useUsageCall(command, params, ready) {
  const key = `${command}|${JSON.stringify(params)}`;
  const [data, setData] = useState(() => _cache.get(key) ?? null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!ready) {
      setData(null);
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    setData(_cache.has(key) ? _cache.get(key) : null);
    setLoading(true);
    invoke(command, params)
      .then((d) => {
        if (cancelled) return;
        const next = d || null;
        if (next) _cache.set(key, next);
        setData(next ?? _cache.get(key) ?? null);
      })
      .catch(() => {
        if (!cancelled) setData(_cache.get(key) ?? null);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [command, key, ready]);
  if (!data) return { days: [], priceOut: undefined, loading };
  return { days: toUsageDays(data.days), priceOut: data.priceOut, loading };
}

export function useUsageDaily(profile, connectionId = null) {
  return useUsageCall(
    "usage_daily",
    { profile, ...(connectionId ? { connectionId } : {}) },
    !!profile,
  );
}

export function useWorkgroupUsageDaily(profile, wgId, connectionId = null) {
  return useUsageCall(
    "workgroup_usage_daily",
    { profile, wgId, ...(connectionId ? { connectionId } : {}) },
    !!profile && !!wgId,
  );
}

export function _clearUsageCache() {
  _cache.clear();
}
