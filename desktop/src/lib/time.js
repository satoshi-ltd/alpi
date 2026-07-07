const SHORT = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const LONG = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
});
const CLOCK = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });

const DATE_BUCKETS = ["Today", "Yesterday", "This week", "This month", "Earlier"];

export function dateBucket(unixSeconds, nowMs = Date.now()) {
  const now = new Date(nowMs);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = 86400000;
  const ts = (unixSeconds || 0) * 1000;
  if (ts >= startOfToday) return "Today";
  if (ts >= startOfToday - day) return "Yesterday";
  if (ts >= startOfToday - 7 * day) return "This week";
  if (ts >= startOfToday - 30 * day) return "This month";
  return "Earlier";
}

export function groupByDate(rows, getTs, nowMs = Date.now()) {
  const buckets = new Map();
  for (const r of rows || []) {
    const label = dateBucket(getTs(r), nowMs);
    if (!buckets.has(label)) buckets.set(label, []);
    buckets.get(label).push(r);
  }
  return DATE_BUCKETS.filter((l) => buckets.has(l)).map((label) => ({ label, rows: buckets.get(label) }));
}

export function notificationTime(unixSeconds, nowMs = Date.now()) {
  if (!unixSeconds) return "";
  if (dateBucket(unixSeconds, nowMs) === "Today") {
    return CLOCK.format(new Date(unixSeconds * 1000));
  }
  return relativeTime(unixSeconds);
}

export function relativeTime(unixSeconds) {
  if (!unixSeconds) return "";
  const ms = unixSeconds * 1000;
  const now = Date.now();
  const diff = Math.max(0, now - ms);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(diff / 3600000);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(diff / 86400000);
  if (days < 7) return `${days}d`;
  const weeks = Math.floor(days / 7);
  if (weeks < 4) return `${weeks}w`;
  const date = new Date(ms);
  if (date.getFullYear() === new Date(now).getFullYear()) {
    return SHORT.format(date);
  }
  return LONG.format(date);
}
