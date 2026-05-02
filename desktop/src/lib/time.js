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
  const hours = Math.floor(minutes / 60);
  if (hours < 24 && sameDay(ms, now)) return `${hours}h`;
  if (isYesterday(ms, now)) return "yesterday";
  const days = Math.floor(diff / 86400000);
  if (days < 7) return `${days}d`;
  const date = new Date(ms);
  if (date.getFullYear() === new Date(now).getFullYear()) {
    return SHORT.format(date);
  }
  return LONG.format(date);
}

function sameDay(a, b) {
  const da = new Date(a);
  const db = new Date(b);
  return (
    da.getFullYear() === db.getFullYear() &&
    da.getMonth() === db.getMonth() &&
    da.getDate() === db.getDate()
  );
}

function isYesterday(a, now) {
  const da = new Date(a);
  const dn = new Date(now);
  dn.setDate(dn.getDate() - 1);
  return (
    da.getFullYear() === dn.getFullYear() &&
    da.getMonth() === dn.getMonth() &&
    da.getDate() === dn.getDate()
  );
}
