import { pluralize } from "../../../common/pluralize.mjs";
import { daysAhead, formatDay, formatSoon, relativeTime } from "../lib/time.js";

export const MAX_NEEDS_ROWS = 4;
export const MAX_RUNNING_ROWS = 4;
export const MAX_NEXT_ROWS = 3;
export const ROW_BUDGET = 5;
const NEEDS_FULL = 3;
const NEXT_WITH_RUNNING = 2;
const SOON_MS = 6 * 3600000;
const NOT_ONLINE = ["offline", "starting", "connecting"];
export const TRAY_STATES = ["quiet", "needs", "running", "failing", "offline", "starting", "connecting", "online"];

export function trayState({ link = "online", needs = 0, failing = 0, running = 0 } = {}) {
  if (link === "starting") return "starting";
  if (link === "connecting") return "connecting";
  if (link === "offline") return "offline";
  if (needs > 0) return "needs";
  if (failing > 0) return "failing";
  if (running > 0) return "running";
  return "quiet";
}

const count = (n) => (Number.isFinite(n) && n > 0 ? Math.floor(n) : 0);

const capital = (text) => (text ? text[0].toUpperCase() + text.slice(1) : "");

function distinct(rows) {
  return [...new Set((rows ?? []).map((r) => r.label || r.profile).filter(Boolean))];
}

function breakdown(needs) {
  const parts = [];
  const approvals = count(needs.approvals);
  const questions = count(needs.questions);
  if (approvals) parts.push(`${approvals} ${pluralize(approvals, "approval")}`);
  if (questions) parts.push(`${questions} ${pluralize(questions, "question")}`);
  return parts.join(", ");
}

function nextIn(snapshot, nowMs) {
  const at = snapshot.next?.rows?.[0]?.at;
  const ms = at ? Date.parse(at) : NaN;
  if (Number.isNaN(ms)) return "";
  if (ms - nowMs < SOON_MS) {
    const soon = formatSoon(at, nowMs);
    return soon === "now" ? "next due now" : `next ${soon}`;
  }
  const days = daysAhead(ms, nowMs);
  if (days <= 0) return `next at ${formatSoon(at, nowMs)}`;
  return days === 1 ? "next tomorrow" : `next ${formatDay(ms, days)}`;
}

function summary(snapshot, nowMs) {
  const when = nextIn(snapshot, nowMs);
  if (snapshot.state === "needs") {
    const running = count(snapshot.running?.count);
    const lead = running ? `${running} running` : breakdown(snapshot.needs);
    return [lead, when].filter(Boolean).join(" · ") || "Open alpi to review";
  }
  if (when) return `Nothing needs you · ${when}`;
  if (snapshot.member || snapshot.next === undefined) return "Nothing needs you";
  return "Nothing needs you, nothing scheduled";
}

function needsTitle(snapshot) {
  const n = count(snapshot.needs.total);
  const first = snapshot.needs.rows?.[0];
  if (n === 1) return first ? `${capital(first.label || first.profile || "Something")} needs you` : "1 needs you";
  return `${n} need you`;
}

function runningTitle(snapshot) {
  const running = snapshot.running;
  const n = count(running.count);
  const names = (running.rows ?? []).length >= n ? distinct(running.rows) : [];
  if (names.length === 1) return `${capital(names[0])} is working`;
  return `${n} working`;
}

function failingWho(failing) {
  const names = failing.profiles ?? [];
  const extra = count(failing.profileCount) - names.length;
  if (names.length === 2 && extra <= 0) return `${names[0]} and ${names[1]}`;
  if (names.length >= 2) return `${names.join(", ")} and ${extra > 0 ? extra : 1} more`;
  return names[0] ?? "";
}

function offlineCopy(offline) {
  if (offline?.canStart) return { title: "alpi isn’t running", sub: "It is installed on this computer." };
  if (offline?.absent) return { title: "alpi isn’t installed", sub: "Open alpi to set it up." };
  if (offline?.local) return { title: "alpi isn’t running", sub: "Open alpi to see why." };
  return { title: "Can’t reach alpi", sub: "Check the connection in alpi." };
}

function heading(snapshot, nowMs) {
  const { state } = snapshot;
  if (state === "offline") return offlineCopy(snapshot.offline);
  if (state === "starting") return { title: "Starting alpi…", sub: "Waiting for the daemon" };
  if (state === "connecting") return { title: "Connecting…", sub: "Waiting for the daemon" };
  if (state === "online") return { title: "alpi", sub: "online" };
  const sub = summary(snapshot, nowMs);
  if (state === "needs") return { title: needsTitle(snapshot), sub };
  if (state === "failing") {
    const n = count(snapshot.failing.jobs);
    return { title: `${n} ${n === 1 ? "job" : "jobs"} failing`, sub };
  }
  if (state === "running") return { title: runningTitle(snapshot), sub };
  return { title: "All quiet", sub };
}

function fit(total, cap, space) {
  const shown = Math.min(cap, space);
  return Math.max(0, total > shown ? Math.min(cap, space - 1) : shown);
}

function elapsed(ts, nowMs) {
  const rel = relativeTime(ts, nowMs);
  return rel === "now" ? "<1m" : rel;
}

function who(r) {
  return { name: r.label || r.profile || "", connection: r.source || null };
}

function row(r, nowMs) {
  const kind = r.kind === "question" ? "question" : "approval";
  return {
    key: r.id,
    kind,
    title: r.title || (kind === "question" ? "has a question" : "wants to run a command"),
    ...who(r),
    meta: [kind, relativeTime(r.ts, nowMs)].filter(Boolean).join(" · "),
    profile: r.profile ?? null,
    shape: r.shape ?? null,
    accent: r.accent ?? null,
    deeplink: r.deeplink ?? null,
  };
}

function nextRow(r, nowMs) {
  const { name, connection } = who(r);
  return {
    key: r.id,
    title: r.title || name,
    name,
    connection,
    when: formatSoon(r.at, nowMs),
    shape: r.shape ?? null,
    accent: r.accent ?? null,
    deeplink: r.deeplink ?? null,
  };
}

function dayOf(at, nowMs) {
  const ms = Date.parse(at);
  if (Number.isNaN(ms)) return "Later today";
  const days = daysAhead(ms, nowMs);
  return days <= 0 ? "Later today" : formatDay(ms, days);
}

function groupByDay(source, nowMs) {
  const groups = [];
  for (const r of source) {
    const day = dayOf(r.at, nowMs);
    const last = groups[groups.length - 1];
    if (last && last.day === day) last.rows.push(nextRow(r, nowMs));
    else groups.push({ day, rows: [nextRow(r, nowMs)] });
  }
  return groups;
}

function runRow(r, nowMs) {
  const { name, connection } = who(r);
  return {
    key: r.id,
    title: r.title || name,
    name,
    connection,
    elapsed: elapsed(r.ts, nowMs),
    shape: r.shape ?? null,
    accent: r.accent ?? null,
    deeplink: r.deeplink ?? null,
  };
}

export function trayModel(snapshot, nowMs = Date.now()) {
  const s = snapshot && typeof snapshot === "object" ? snapshot : {};
  const state = TRAY_STATES.includes(s.state) ? s.state : "quiet";
  const c = s.counts ?? {};
  const view = {
    ...s,
    state,
    needs: { ...s.needs, total: s.needs?.total ?? c.needs },
    failing: { ...s.failing, jobs: s.failing?.jobs ?? c.failing },
    running: { ...s.running, count: s.running?.count ?? c.running },
  };
  const { title, sub } = heading(view, nowMs);
  const online = !NOT_ONLINE.includes(state);
  const needs = view.needs;
  const counts = [];
  const failingJobs = count(view.failing.jobs);
  const runningCount = count(view.running.count);
  const failing = online && failingJobs > 0
    ? { title: `${failingJobs} ${failingJobs === 1 ? "job" : "jobs"} failed in 24 h`, detail: failingWho(view.failing) }
    : null;
  const needsTotal = count(needs.total);
  const needsRows = online ? needs.rows ?? [] : [];
  const rows = needsRows.slice(0, fit(Math.max(needsTotal, needsRows.length), MAX_NEEDS_ROWS, ROW_BUDGET - (failing ? 1 : 0))).map((r) => row(r, nowMs));
  const more = rows.length > 0 ? Math.max(0, needsTotal - rows.length) : 0;
  if (online && needsTotal > 0 && rows.length === 0) counts.push({ key: "needs", icon: "clock", label: "Needs you", value: String(needsTotal), danger: false });
  const needsFull = rows.length >= NEEDS_FULL;
  let budget = ROW_BUDGET - rows.length - (more > 0 ? 1 : 0) - (failing ? 1 : 0);
  const runRows = online && !needsFull ? view.running.rows ?? [] : [];
  const runs = runRows.slice(0, fit(Math.max(runningCount, runRows.length), MAX_RUNNING_ROWS, budget)).map((r) => runRow(r, nowMs));
  const runsMore = runs.length > 0 ? Math.max(0, runningCount - runs.length) : 0;
  budget -= runs.length + (runsMore > 0 ? 1 : 0);
  if (online && runningCount > 0 && runs.length === 0) counts.push({ key: "running", icon: "activity", label: "Running", value: String(runningCount), danger: false });
  const update = s.update
    ? { text: s.update.version ? `alpi ${s.update.version} is ready` : "An update is ready", busy: Boolean(s.update.busy) }
    : null;
  const unread = count(s.unread);
  const nextCap = Math.min(runs.length > 0 ? NEXT_WITH_RUNNING : MAX_NEXT_ROWS, budget);
  const nextRows = online && !needsFull && s.next?.rows ? s.next.rows.slice(0, Math.max(0, nextCap)) : [];
  return {
    nextGroups: groupByDay(nextRows, nowMs),
    state,
    title,
    sub,
    rows,
    more,
    runs,
    runsMore,
    counts,
    failing,
    busy: state === "starting" ? "Start requested" : null,
    start: state === "offline" && Boolean(s.offline?.canStart),
    update,
    unread,
    bell: !s.member,
    bellLabel: unread > 0 ? `Notifications · ${unread} unread` : "Notifications",
  };
}
