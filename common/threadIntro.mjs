export const CONTINUE_LABEL = "Continue";

const oneLine = (value) => String(value ?? "").replace(/\s+/g, " ").trim();

export function introBio(profile) {
  return oneLine(profile?.bio ?? profile?.public_bio) || null;
}

export function introSession(profile) {
  const latest = profile?.latest_session;
  if (!latest?.id || (latest.kind && latest.kind !== "chat")) return null;
  const title = oneLine(latest.first_user);
  if (!title) return null;
  return { id: latest.id, title, ts: latest.updated_at || latest.mtime || latest.started_at || 0 };
}

const SHORT = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const LONG = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });

export function introAge(unixSeconds, nowMs = Date.now()) {
  if (!unixSeconds) return "";
  const ms = unixSeconds * 1000;
  const minutes = Math.floor(Math.max(0, nowMs - ms) / 60000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  if (days < 28) return `${Math.floor(days / 7)}w`;
  const date = new Date(ms);
  return (date.getFullYear() === new Date(nowMs).getFullYear() ? SHORT : LONG).format(date);
}
