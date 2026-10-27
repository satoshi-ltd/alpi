import { groupActivity } from "../../../common/activityGroups.mjs";
import { trayState, MAX_NEEDS_ROWS, MAX_RUNNING_ROWS, MAX_NEXT_ROWS } from "../tray/trayModel.js";
import { profileLabel } from "./profile-display.js";

export const TRAY_SNAPSHOT_VERSION = 1;

export const MAX_TEXT = 200;
export const MAX_VERSION = 32;

export const clip = (value, max = MAX_TEXT) => {
  const text = String(value ?? "");
  if (text.length <= max) return text;
  let out = "";
  for (const point of text) {
    if (out.length + point.length > max - 1) break;
    out += point;
  }
  return `${out}…`;
};

const CONNECTING = new Set(["unknown", "probing"]);

export function trayLink({ connection, daemon }) {
  if (!connection) return "connecting";
  if (connection.status === "online") return "online";
  const local = connection.kind === "local";
  if (local && (daemon?.phase === "starting" || daemon?.phase === "installing")) return "starting";
  if (local && daemon?.launched && daemon?.phase === "idle") return "starting";
  if (connection.status == null || CONNECTING.has(connection.status)) return "connecting";
  return "offline";
}

function needsRows(items, { connectionId, foldByProfile, accentByProfile }) {
  return items.slice(0, MAX_NEEDS_ROWS).map((item) => {
    const question = item.kind === "clarification";
    return {
      id: String(item.request_id),
      kind: question ? "question" : "approval",
      profile: item.profile ?? null,
      label: clip(profileLabel(item.profile ?? "")),
      title: clip(item.title),
      ts: Number.isFinite(item.ts) ? item.ts : null,
      fold: foldByProfile?.[item.profile] ?? null,
      accent: accentByProfile?.[item.profile] ?? null,
      deeplink: { kind: question ? "clarification" : "approval", profile: item.profile ?? null, id: String(item.request_id), connection_id: connectionId ?? "" },
    };
  });
}

function runDeeplink(item, connectionId) {
  const profile = item.profile ?? null;
  if (!profile) return null;
  const connection_id = connectionId ?? "";
  if (item.kind === "workgroup" && item.workgroup_id) return { kind: "workgroup", profile, id: String(item.workgroup_id), connection_id };
  if (item.session_id) return { kind: "chat", profile, id: String(item.session_id), connection_id };
  return { kind: "profile", profile, id: profile, connection_id };
}

function runningRows(items, { connectionId, foldByProfile, accentByProfile }) {
  const seen = new Map();
  return items.slice(0, MAX_RUNNING_ROWS).map((item) => {
    const profile = item.profile ?? null;
    const base = `${profile ?? ""}/${item.workgroup_id ?? item.job_id ?? item.session_id ?? ""}`;
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    return {
      id: n ? `${base}#${n}` : base,
      profile,
      label: clip(profileLabel(profile ?? "")),
      title: clip(item.title || item.name),
      ts: Number.isFinite(item.started_at) ? item.started_at : null,
      fold: foldByProfile?.[profile] ?? null,
      accent: accentByProfile?.[profile] ?? null,
      deeplink: runDeeplink(item, connectionId),
    };
  });
}

export function buildTraySnapshot({
  connection = null,
  daemon = null,
  activity = null,
  activitySupported = true,
  member = false,
  unread = 0,
  update = null,
  foldByProfile = {},
  accentByProfile = {},
  otherSchedules = [],
  nowMs = Date.now(),
} = {}) {
  const rawLink = trayLink({ connection, daemon });
  const online = rawLink === "online";
  const loading = online && activitySupported && activity == null;
  const unsupported = online && !activitySupported;
  const link = loading ? "connecting" : rawLink;
  const groups = groupActivity(online && activitySupported ? activity : null, { nowMs });
  const failingProfiles = member ? [] : groups.failing;
  const failingJobs = failingProfiles.reduce((n, g) => n + g.count, 0);
  const needs = groups.needs;
  const approvals = needs.filter((i) => i.kind !== "clarification").length;
  const counts = { needs: needs.length, failing: failingJobs, running: groups.running.length };
  const local = connection?.kind === "local";
  const unreadCount = member ? 0 : Math.max(0, Math.floor(Number(unread) || 0));
  const known = !member && online && activitySupported && activity != null;
  const activeName = connection?.name ?? connection?.id ?? "";
  const candidates = known
    ? [
        ...groups.upcoming.map((job) => ({ job, id: connection?.id, name: activeName, folds: foldByProfile, accents: accentByProfile })),
        ...otherSchedules.filter((other) => other.id !== connection?.id).flatMap((other) =>
          groupActivity({ scheduled: other.scheduled }, { nowMs }).upcoming.map((job) => ({ job, id: other.id, name: other.name ?? other.id ?? "", folds: other.folds, accents: other.accents })),
        ),
      ]
    : [];
  const several = new Set(candidates.map((c) => c.id)).size > 1;
  const nextRows = known
    ? candidates
        .sort((a, b) => a.job.nextAt - b.job.nextAt)
        .slice(0, MAX_NEXT_ROWS)
        .map(({ job, id, name, folds, accents }) => ({
          id: `${id ?? ""}/${job.profile ?? ""}/${job.job_id ?? ""}`,
          title: clip(job.title || job.job_id),
          label: clip(profileLabel(job.profile ?? "")),
          at: new Date(job.nextAt * 1000).toISOString(),
          source: several ? clip(name, 40) : null,
          fold: folds?.[job.profile] ?? null,
          accent: accents?.[job.profile] ?? null,
          deeplink: job.profile ? { kind: "settings", profile: job.profile, id: "schedules", connection_id: id ?? "" } : null,
        }))
    : [];
  return {
    v: TRAY_SNAPSHOT_VERSION,
    state: unsupported ? "online" : trayState({ link, ...counts }),
    counts,
    member: Boolean(member),
    unread: unreadCount,
    update: update ? { version: update.version == null ? null : clip(update.version, MAX_VERSION), busy: Boolean(update.busy) } : null,
    needs: {
      total: needs.length,
      approvals,
      questions: needs.length - approvals,
      rows: needsRows(needs, { connectionId: connection?.id, foldByProfile, accentByProfile }),
    },
    failing: {
      jobs: failingJobs,
      profileCount: failingProfiles.length,
      profiles: failingProfiles.slice(0, 2).map((g) => clip(profileLabel(g.profile ?? ""))),
    },
    running: {
      count: counts.running,
      rows: runningRows(groups.running, { connectionId: connection?.id, foldByProfile, accentByProfile }),
    },
    next: nextRows.length ? { rows: nextRows } : null,
    offline: rawLink === "offline"
      ? { local, canStart: local && daemon?.state === "stopped", absent: local && (daemon?.state === "absent" || daemon?.state === "unsupported") }
      : null,
  };
}
