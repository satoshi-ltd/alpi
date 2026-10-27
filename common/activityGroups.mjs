export const ACTIVITY_FILTERS = ["all", "needs", "failing", "running", "upcoming"];
export const FAILED_WINDOW_S = 24 * 60 * 60;

export function toEpochSeconds(value) {
  if (value == null || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? (value > 1e12 ? value / 1000 : value) : null;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms / 1000;
}

const list = (v) => (Array.isArray(v) ? v.filter((x) => x && typeof x === "object") : []);

export function stripProfilePrefix(title, ...names) {
  const text = String(title ?? "");
  for (const name of names) {
    if (!name) continue;
    const head = text.slice(0, name.length);
    if (head.toLowerCase() !== name.toLowerCase()) continue;
    const rest = text.slice(name.length).replace(/^[\s·:\-–—]+/, "");
    if (rest && rest !== text.slice(name.length)) return rest;
  }
  return text;
}

export function groupActivity(activity, { nowMs = Date.now() } = {}) {
  const nowS = nowMs / 1000;
  const needs = list(activity?.needs_you);
  const running = list(activity?.running);
  const rerunning = new Set(running.filter((r) => r.job_id).map((r) => `${r.profile}/${r.job_id}`));
  const byProfile = new Map();
  const upcoming = [];
  for (const job of list(activity?.scheduled)) {
    const failedAt = job.last_run_status === "error" ? toEpochSeconds(job.last_run_at) : null;
    if (rerunning.has(`${job.profile}/${job.job_id}`)) continue;
    const failing = failedAt != null && nowS - failedAt <= FAILED_WINDOW_S;
    if (failing) {
      const row = { ...job, failedAt, lastOkAt: toEpochSeconds(job.last_ok_at) };
      const group = byProfile.get(job.profile) ?? { profile: job.profile, jobs: [], latestAt: 0 };
      group.jobs.push(row);
      group.latestAt = Math.max(group.latestAt, failedAt);
      byProfile.set(job.profile, group);
      continue;
    }
    const nextAt = toEpochSeconds(job.next_fire);
    if (nextAt != null && nextAt > nowS) upcoming.push({ ...job, nextAt });
  }
  const failing = [...byProfile.values()]
    .map((g) => ({ ...g, count: g.jobs.length, jobs: g.jobs.sort((a, b) => b.failedAt - a.failedAt) }))
    .sort((a, b) => b.latestAt - a.latestAt || String(a.profile).localeCompare(String(b.profile)));
  upcoming.sort((a, b) => a.nextAt - b.nextAt);
  const failingCount = failing.reduce((n, g) => n + g.count, 0);
  const counts = { needs: needs.length, failing: failingCount, running: running.length, upcoming: upcoming.length };
  return { needs, failing, running, upcoming, counts: { all: needs.length + failingCount + running.length + upcoming.length, ...counts } };
}

export function applyFilter(groups, filter = "all") {
  if (!ACTIVITY_FILTERS.includes(filter) || filter === "all") return groups;
  return {
    ...groups,
    needs: filter === "needs" ? groups.needs : [],
    failing: filter === "failing" ? groups.failing : [],
    running: filter === "running" ? groups.running : [],
    upcoming: filter === "upcoming" ? groups.upcoming : [],
  };
}

export function failingJobs(groups) {
  return groups.failing.flatMap((g) => g.jobs);
}

export const UPCOMING_CAP = 10;

export function visibleFilters(counts, current = "all") {
  const filled = ACTIVITY_FILTERS.filter((id) => id !== "all" && counts?.[id] > 0);
  if (filled.length < 2 && current === "all") return [];
  return ACTIVITY_FILTERS.filter((id) => id === "all" || id === current || counts?.[id] > 0);
}

export function nextRun(groups) {
  return groups.upcoming[0] ?? null;
}

const startOfDay = (ms) => {
  const d = new Date(ms);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
};

export function groupByDay(rows, { nowMs = Date.now() } = {}) {
  const today = startOfDay(nowMs);
  const days = [];
  for (const row of rows) {
    const start = startOfDay(row.nextAt * 1000);
    const last = days[days.length - 1];
    if (last && last.start === start) last.rows.push(row);
    else days.push({ start, days: Math.max(0, Math.round((start - today) / 86400000)), rows: [row] });
  }
  return days;
}

export function capDays(days, limit = UPCOMING_CAP) {
  let left = limit;
  const shown = [];
  for (const day of days) {
    if (left <= 0) break;
    const rows = day.rows.slice(0, left);
    left -= rows.length;
    shown.push({ ...day, rows, total: day.rows.length });
  }
  const total = days.reduce((n, day) => n + day.rows.length, 0);
  return { days: shown, hidden: total - (limit - left) };
}
