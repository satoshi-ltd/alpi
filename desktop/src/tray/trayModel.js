import { pluralize } from "../../../common/pluralize.mjs";
import { formatNextFire, relativeTime } from "../lib/time.js";

export const MAX_NEEDS_ROWS = 4;
export const MAX_RUNNING_ROWS = 4;
export const MAX_NEXT_ROWS = 3;
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

function sentence(row) {
  return row.kind === "question" ? `${row.label} has a question` : `${row.label} is waiting for an approval`;
}

function needsSub(needs) {
  const total = count(needs.total);
  if (total <= 2 && needs.rows?.[0]) return sentence(needs.rows[0]);
  const parts = [];
  const approvals = count(needs.approvals);
  const questions = count(needs.questions);
  if (approvals) parts.push(`${approvals} ${pluralize(approvals, "approval")}`);
  if (questions) parts.push(`${questions} ${pluralize(questions, "question")}`);
  return parts.join(", ");
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
  const needs = snapshot.needs ?? {};
  const failing = snapshot.failing ?? {};
  const running = snapshot.running ?? {};
  if (state === "needs") {
    const n = count(needs.total);
    return { title: `${n} ${pluralize(n, "needs", "need")} you`, sub: needsSub(needs) };
  }
  if (state === "failing") {
    const n = count(failing.jobs);
    return { title: `${n} ${pluralize(n, "job")} failing`, sub: failingSub(failing) };
  }
  if (state === "running") {
    return { title: `${count(running.count)} running`, sub: "Working now" };
  }
  if (state === "offline") return offlineCopy(snapshot.offline);
  if (state === "starting") return { title: "Starting alpi…", sub: "Waiting for the daemon" };
  if (state === "online") return { title: "alpi", sub: "online" };
  if (state === "connecting") return { title: "Connecting…", sub: "Waiting for the daemon" };
  if (snapshot.member || snapshot.next === undefined) return { title: "All quiet", sub: "Nothing needs you · online" };
  if (snapshot.next === null) return { title: "All quiet", sub: "Nothing scheduled" };
  return { title: "All quiet", sub: "Coming up" };
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
  const parts = [r.label, kind, ago(r.ts, nowMs)].filter(Boolean);
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
    sub: label ? `${label} · running` : "running",
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
  const runs = online && state === "running" ? (view.running.rows ?? []).slice(0, MAX_RUNNING_ROWS).map((r) => runRow(r, nowMs)) : [];
  const runsMore = runs.length > 0 ? Math.max(0, runningCount - runs.length) : 0;
  if (online && runningCount > 0 && runs.length === 0) counts.push({ key: "running", icon: "activity", label: "Running", value: String(runningCount), danger: false });
  const update = s.update
    ? { text: s.update.version ? `alpi ${s.update.version} is ready` : "An update is ready", busy: Boolean(s.update.busy) }
    : null;
  const unread = count(s.unread);
  const quiet = state === "quiet";
  const nextRows = quiet && !s.member && s.next?.rows ? s.next.rows.slice(0, MAX_NEXT_ROWS).map((r) => nextRow(r, nowMs)) : [];
  return {
    nextRows,
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
