import { dateBucket } from "./notificationTriage.mjs";

const CLOCK = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const WEEKDAY = new Intl.DateTimeFormat(undefined, { weekday: "short" });
const DATE = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const DATE_YEAR = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });
const STAMP = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
const STAMP_YEAR = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });

const sameYear = (at, nowMs) => at.getFullYear() === new Date(nowMs).getFullYear();

export function notificationTime(unixSeconds, { nowMs = Date.now(), dayGroup = true } = {}) {
  if (!unixSeconds) return "";
  const at = new Date(unixSeconds * 1000);
  const bucket = dateBucket(unixSeconds, nowMs);
  if (bucket === "Today") return CLOCK.format(at);
  if (bucket === "Yesterday") return dayGroup ? CLOCK.format(at) : "Yesterday";
  if (bucket === "This week") return dayGroup ? `${WEEKDAY.format(at)} ${CLOCK.format(at)}` : WEEKDAY.format(at);
  return (sameYear(at, nowMs) ? DATE : DATE_YEAR).format(at);
}

export function notificationStamp(unixSeconds, nowMs = Date.now()) {
  if (!unixSeconds) return "";
  const at = new Date(unixSeconds * 1000);
  const bucket = dateBucket(unixSeconds, nowMs);
  if (bucket === "Today" || bucket === "Yesterday") return `${bucket} ${CLOCK.format(at)}`;
  return (sameYear(at, nowMs) ? STAMP : STAMP_YEAR).format(at);
}
