import { invoke } from "@tauri-apps/api/core";
import { createSwrCache } from "../lib/swr-cache.js";
import { useSwrValue } from "./useSwrValue.js";

const WEEKDAY_INITIALS = ["S", "M", "T", "W", "T", "F", "S"];

const _cache = createSwrCache({
  fetcher: ({ command, params }) => invoke(command, params).then((d) => d || null),
});

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

function useUsageCall(command, params, ready, prefetched, defer = false) {
  const key = `${params.connectionId || "local"}|${command}|${JSON.stringify(params)}`;
  const { data, loading } = useSwrValue(
    _cache,
    key,
    { command, params },
    { enabled: ready, defer, prefetched },
  );
  if (prefetched !== undefined) {
    return {
      days: toUsageDays(prefetched?.days),
      priceOut: prefetched?.priceOut,
      total30: prefetched?.total30 ?? null,
      loading: false,
    };
  }
  if (!data) return { days: [], priceOut: undefined, total30: null, loading };
  return { days: toUsageDays(data.days), priceOut: data.priceOut, total30: data.total30 ?? null, loading };
}

export function useUsageDaily(profile, connectionId = null, prefetched, defer = false) {
  return useUsageCall(
    "usage_daily",
    { profile, ...(connectionId ? { connectionId } : {}) },
    !!profile,
    prefetched,
    defer,
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
