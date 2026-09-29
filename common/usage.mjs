const WEEKDAY_INITIALS = ["S", "M", "T", "W", "T", "F", "S"];

export const PRICE_IN = 0.15 / 1e6;
export const PRICE_OUT = 0.6 / 1e6;
export const SCALE_HEADROOM = 1.08;
export const MIN_BAR_PX = 3;

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

export function costOf(d) {
  if (d.cost != null) return d.cost;
  return (d.tokIn || 0) * PRICE_IN + (d.tokOut || 0) * PRICE_OUT;
}

export function tokensOf(d) {
  return (d.tokIn || 0) + (d.tokOut || 0);
}

export function usageTotals(days) {
  return (days || []).reduce(
    (acc, d) => ({
      cost: acc.cost + costOf(d),
      tokIn: acc.tokIn + (d.tokIn || 0),
      tokOut: acc.tokOut + (d.tokOut || 0),
    }),
    { cost: 0, tokIn: 0, tokOut: 0 },
  );
}

export function todayOf(days) {
  if (!days?.length) return null;
  return days.find((d) => d.today) ?? days[days.length - 1];
}

export function usageScale(days) {
  const maxTok = Math.max(0, ...(days || []).map(tokensOf));
  return (maxTok || 1) * SCALE_HEADROOM;
}

export function pctLeft(cost, cap) {
  if (typeof cap !== "number" || cap <= 0) return null;
  return Math.max(0, Math.round((1 - cost / cap) * 100));
}

export function barHeights(d, scale, chartHeight) {
  const tok = tokensOf(d);
  const total = (tok / scale) * chartHeight;
  const out = tok > 0 ? Math.min(total, ((d.tokOut || 0) / scale) * chartHeight) : 0;
  return { total: Math.max(tok > 0 ? MIN_BAR_PX : 0, total), out };
}
