const DATE_BUCKETS = ["Today", "Yesterday", "This week", "This month", "Earlier"];
const DAY_MS = 86400000;

export const NOTIFICATION_FILTERS = [
  { id: "all", label: "All" },
  { id: "needs", label: "Needs you" },
  { id: "unread", label: "Unread" },
];

export function dateBucket(unixSeconds, nowMs = Date.now()) {
  const now = new Date(nowMs);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const ts = (unixSeconds || 0) * 1000;
  if (ts >= startOfToday) return "Today";
  if (ts >= startOfToday - DAY_MS) return "Yesterday";
  if (ts >= startOfToday - 7 * DAY_MS) return "This week";
  if (ts >= startOfToday - 30 * DAY_MS) return "This month";
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

export const notificationKey = (row) => `${row?.connectionId}:${row?.profile}:${row?.id}`;

export function isNeedsYou(row, unread) {
  return !!unread && (row?.type === "error" || row?.type === "warning");
}

export function triageCounts(rows, isUnread) {
  const list = rows || [];
  return {
    all: list.length,
    needs: list.filter((r) => isNeedsYou(r, isUnread(r))).length,
    unread: list.filter(isUnread).length,
  };
}

export function filterNotifications(rows, filter, { isUnread, frozen = null } = {}) {
  const list = rows || [];
  const kept = (r, flag) => frozen?.key === notificationKey(r) && !!frozen[flag];
  if (filter === "needs") return list.filter((r) => isNeedsYou(r, isUnread(r)) || kept(r, "pinned"));
  if (filter === "unread") return list.filter((r) => isUnread(r) || kept(r, "unread"));
  return list;
}

export function groupNotifications(rows, { filter, isUnread, frozen = null, nowMs = Date.now() } = {}) {
  const list = rows || [];
  const pinnedOf = (r) => (frozen?.key === notificationKey(r) ? !!frozen.pinned : isNeedsYou(r, isUnread(r)));
  const pinned = filter === "unread" ? [] : list.filter(pinnedOf);
  const pinnedKeys = new Set(pinned.map(notificationKey));
  const rest = groupByDate(list.filter((r) => !pinnedKeys.has(notificationKey(r))), (r) => r.created_at, nowMs)
    .map((g) => ({ id: `day:${g.label}`, ...g }));
  return pinned.length ? [{ id: "needs", label: `Needs you · ${pinned.length}`, rows: pinned }, ...rest] : rest;
}
