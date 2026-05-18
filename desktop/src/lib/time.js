const SHORT = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const LONG = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
});

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
