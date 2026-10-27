import { pluralize } from "../../../common/pluralize.mjs";
import { formatNextFire, relativeTime } from "../lib/time.js";

export const MAX_NEEDS_ROWS = 4;
export const MAX_RUNNING_ROWS = 4;
export const MAX_NEXT_ROWS = 3;
export const ROW_BUDGET = 5;
const NEEDS_FULL = 3;
const NEXT_WITH_RUNNING = 2;
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

function enumerate(names) {
  if (names.length <= 1) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

function breakdown(needs) {
  const parts = [];
  const approvals = count(needs.approvals);
  const questions = count(needs.questions);
  if (approvals) parts.push(`${approvals} ${pluralize(approvals, "approval")}`);
  if (questions) parts.push(`${questions} ${pluralize(questions, "question")}`);
  return parts.join(", ");
}

function aside(snapshot) {
  const parts = [];
  const running = count(snapshot.running?.count);
  const next = count(snapshot.next?.total ?? snapshot.next?.rows?.length);
  if (running) parts.push(`${running} running`);
  if (next) parts.push(`${next} coming up`);
  return parts;
}

function needsHeading(snapshot) {
  const needs = snapshot.needs;
  const n = count(needs.total);
  const first = needs.rows?.[0];
  if (n === 1) {
    const rest = aside(snapshot);
    if (!first) return { title: "1 thing needs you", sub: breakdown(needs) };
    const fallback = [first.kind === "question" ? "Has a question" : "Waiting for an approval", first.source].filter(Boolean).join(" · ");
    return { title: `${capital(first.label || first.profile || "Something")} needs you`, sub: rest.length ? rest.join(" · ") : fallback };
  }
  const names = distinct(needs.rows);
  const title = `${n} things need you`;
  if (names.length === 1) return { title, sub: [names[0], breakdown(needs)].filter(Boolean).join(" · ") };
  if (names.length > 3) return { title, sub: `${names.slice(0, 2).join(", ")} and ${names.length - 2} more` };
  return { title, sub: names.length ? enumerate(names) : breakdown(needs) };
}

function runningHeading(snapshot, nowMs) {
  const running = snapshot.running;
  const n = count(running.count);
  const names = (running.rows ?? []).length >= n ? distinct(running.rows) : [];
  const rest = aside({ next: snapshot.next });
  const single = n === 1 && running.rows?.[0] ? elapsed(running.rows[0].ts, nowMs) : "";
  const sub = [single, ...rest].filter(Boolean).join(" · ") || "Working now";
  if (names.length === 1) return { title: `${capital(names[0])} is working`, sub };
  if (names.length === 2) return { title: `${capital(names[0])} and ${names[1]} are working`, sub };
  return { title: `${n} running`, sub };
}

function failingSub(failing) {
  const names = failing.profiles ?? [];
  const extra = count(failing.profileCount) - names.length;
  let who = names[0] ?? "";
  if (names.length === 2 && extra <= 0) who = `${names[0]} and ${names[1]}`;
  else if (names.length >= 2) who = `${names.join(", ")} and ${extra > 0 ? extra : 1} more`;
  return who ? `${who} · last 24 h` : "Last 24 h";
}

function offlineCopy(offline) {
  if (offline?.canStart) return { title: "alpi is installed but not running", sub: "Start it on this computer." };
  if (offline?.absent) return { title: "alpi isn’t installed", sub: "Open alpi to set it up." };
  if (offline?.local) return { title: "alpi isn’t running", sub: "Open alpi to see why." };
  return { title: "Can’t reach alpi", sub: "Check the connection in alpi." };
}

function heading(snapshot, nowMs) {
  const { state } = snapshot;
  const failing = snapshot.failing ?? {};
  if (state === "needs") return needsHeading(snapshot);
  if (state === "failing") {
    const n = count(failing.jobs);
    return { title: `${n} ${n === 1 ? "job is" : "jobs are"} failing`, sub: failingSub(failing) };
  }
  if (state === "running") return runningHeading(snapshot, nowMs);
  if (state === "offline") return offlineCopy(snapshot.offline);
  if (state === "starting") return { title: "Starting alpi…", sub: "Waiting for the daemon" };
  if (state === "online") return { title: "alpi", sub: "online" };
  if (state === "connecting") return { title: "Connecting…", sub: "Waiting for the daemon" };
  if (snapshot.next?.rows?.length) return { title: "All quiet", sub: "Coming up" };
  if (snapshot.member || snapshot.next === undefined) return { title: "All quiet", sub: "Nothing needs you · online" };
  return { title: "All quiet", sub: "Nothing scheduled" };
}

function elapsed(ts, nowMs) {
  const rel = relativeTime(ts, nowMs);
  return rel === "now" ? "<1m" : rel;
}

function ago(ts, nowMs) {
  const rel = relativeTime(ts, nowMs);
  if (!rel) return "";
  return rel === "now" ? "just now" : `${rel} ago`;
}

function row(r, nowMs) {
  const kind = r.kind === "question" ? "question" : "approval";
  const parts = [r.label, r.source, kind, ago(r.ts, nowMs)].filter(Boolean);
  return {
    key: r.id,
    kind,
    title: r.title || (kind === "question" ? "has a question" : "wants to run a command"),
    sub: parts.join(" · "),
    profile: r.profile ?? null,
    fold: r.fold ?? null,
    accent: r.accent ?? null,
    deeplink: r.deeplink ?? null,
  };
}

function nextRow(r, nowMs) {
  const label = r.label || r.profile || "";
  return {
    key: r.id,
    title: r.title || label,
    sub: [label, r.source].filter(Boolean).join(" · "),
    when: formatNextFire(r.at, nowMs),
    fold: r.fold ?? null,
    accent: r.accent ?? null,
    deeplink: r.deeplink ?? null,
  };
}

function runRow(r, nowMs) {
  const label = r.label || r.profile || "";
  return {
    key: r.id,
    title: r.title || label,
    sub: [label, r.source, "running"].filter(Boolean).join(" · "),
    elapsed: elapsed(r.ts, nowMs),
    fold: r.fold ?? null,
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
  const rows = online ? (needs.rows ?? []).slice(0, MAX_NEEDS_ROWS).map((r) => row(r, nowMs)) : [];
  const more = online ? Math.max(0, count(needs.total) - rows.length) : 0;
  const counts = [];
  const failingJobs = count(view.failing.jobs);
  const runningCount = count(view.running.count);
  if (online && failingJobs > 0) {
    const p = count(view.failing.profileCount);
    counts.push({
      key: "failing",
      icon: "triangle-alert",
      label: "Failing jobs",
      value: p > 0 ? `${failingJobs} in ${p} ${pluralize(p, "profile")}` : String(failingJobs),
      danger: true,
    });
  }
  const needsFull = rows.length >= NEEDS_FULL;
  const budget = ROW_BUDGET - rows.length - (failingJobs > 0 ? 1 : 0);
  const runs = online && !needsFull ? (view.running.rows ?? []).slice(0, Math.max(0, Math.min(MAX_RUNNING_ROWS, budget))).map((r) => runRow(r, nowMs)) : [];
  const runsMore = runs.length > 0 ? Math.max(0, runningCount - runs.length) : 0;
  if (online && runningCount > 0 && runs.length === 0) counts.push({ key: "running", icon: "activity", label: "Running", value: String(runningCount), danger: false });
  const update = s.update
    ? { text: s.update.version ? `alpi ${s.update.version} is ready` : "An update is ready", busy: Boolean(s.update.busy) }
    : null;
  const unread = count(s.unread);
  const nextCap = Math.min(runs.length > 0 ? NEXT_WITH_RUNNING : MAX_NEXT_ROWS, budget - runs.length);
  const nextRows = online && !needsFull && s.next?.rows ? s.next.rows.slice(0, Math.max(0, nextCap)).map((r) => nextRow(r, nowMs)) : [];
  const sections = [rows, runs, nextRows, counts].filter((list) => list.length > 0).length;
  return {
    nextRows,
    labels: sections > 1,
    state,
    title,
    sub,
    rows,
    more,
    runs,
    runsMore,
    counts,
    busy: state === "starting" ? "Start requested" : null,
    start: state === "offline" && Boolean(s.offline?.canStart),
    update,
    unread,
    bell: !s.member,
    bellLabel: unread > 0 ? `Notifications · ${unread} unread` : "Notifications",
  };
}
