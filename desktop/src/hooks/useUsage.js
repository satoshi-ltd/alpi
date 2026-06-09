import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

const WEEKDAY_INITIALS = ["S", "M", "T", "W", "T", "F", "S"];

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
  const [data, setData] = useState(null);
  const key = JSON.stringify(params);
  useEffect(() => {
    if (!ready) {
      setData(null);
      return undefined;
    }
    let cancelled = false;
    invoke(command, params)
      .then((d) => { if (!cancelled) setData(d || null); })
      .catch(() => { if (!cancelled) setData(null); });
    return () => { cancelled = true; };
  }, [command, key, ready]);
  if (!data) return { days: [], priceOut: undefined };
  return { days: toUsageDays(data.days), priceOut: data.priceOut };
}

export function useUsageDaily(profile) {
  return useUsageCall("usage_daily", { profile }, !!profile);
}

export function useWorkgroupUsageDaily(profile, wgId) {
  return useUsageCall(
    "workgroup_usage_daily",
    { profile, wgId },
    !!profile && !!wgId,
  );
}
