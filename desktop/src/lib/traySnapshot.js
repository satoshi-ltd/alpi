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

function needsRows(items) {
  return items.slice(0, MAX_NEEDS_ROWS).map(({ item, source, connectionId, prefix, folds, accents }) => {
    const question = item.kind === "clarification";
    return {
      id: `${prefix}${item.request_id}`,
      kind: question ? "question" : "approval",
      profile: item.profile ?? null,
      label: clip(profileLabel(item.profile ?? "")),
      title: clip(item.title),
      ts: Number.isFinite(item.ts) ? item.ts : null,
      source,
      fold: folds?.[item.profile] ?? null,
      accent: accents?.[item.profile] ?? null,
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

function runningRows(items) {
  const seen = new Map();
  return items.slice(0, MAX_RUNNING_ROWS).map(({ item, source, connectionId, prefix, folds, accents }) => {
    const profile = item.profile ?? null;
    const base = `${prefix}${profile ?? ""}/${item.workgroup_id ?? item.job_id ?? item.session_id ?? ""}`;
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    return {
      id: n ? `${base}#${n}` : base,
      profile,
      label: clip(profileLabel(profile ?? "")),
      title: clip(item.title || item.name),
      ts: Number.isFinite(item.started_at) ? item.started_at : null,
      source,
      fold: folds?.[profile] ?? null,
      accent: accents?.[profile] ?? null,
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
  otherActivity = [],
  nowMs = Date.now(),
} = {}) {
  const rawLink = trayLink({ connection, daemon });
  const online = rawLink === "online";
  const loading = online && activitySupported && activity == null;
  const unsupported = online && !activitySupported;
  const link = loading ? "connecting" : rawLink;
  const activeKnown = online && activitySupported && activity != null;
  const activeName = connection?.name ?? connection?.id ?? "";
  const sources = [
    ...(activeKnown ? [{ id: connection?.id ?? "", name: activeName, member, prefix: "", folds: foldByProfile, accents: accentByProfile, groups: groupActivity(activity, { nowMs }) }] : []),
    ...otherActivity.filter((other) => other.id !== connection?.id).map((other) => ({
      id: other.id,
      name: other.name ?? other.id ?? "",
      member: Boolean(other.member),
      prefix: `${other.id}/`,
      folds: other.folds,
      accents: other.accents,
      groups: groupActivity(other.activity, { nowMs }),
    })),
  ];
  const several = sources.length > 1;
  const tag = (src, item) => ({ item, source: several ? clip(src.name, 40) : null, connectionId: src.id, prefix: src.prefix, folds: src.folds, accents: src.accents });
  const needs = sources.flatMap((src) => src.groups.needs.map((item) => tag(src, item)));
  const running = sources.flatMap((src) => src.groups.running.map((item) => tag(src, item)));
  const failingGroups = sources.flatMap((src) => (src.member ? [] : src.groups.failing.map((group) => ({ group, src }))));
  const failingProfiles = failingGroups.map(({ group }) => group);
  const failingLabels = failingGroups.map(({ group }) => clip(profileLabel(group.profile ?? "")));
  const failingNames = failingGroups.map(({ src }, i) => (failingLabels.indexOf(failingLabels[i]) !== failingLabels.lastIndexOf(failingLabels[i]) ? `${failingLabels[i]} · ${clip(src.name, 40)}` : failingLabels[i]));
  const failingJobs = failingProfiles.reduce((n, g) => n + g.count, 0);
  const approvals = needs.filter(({ item }) => item.kind !== "clarification").length;
  const counts = { needs: needs.length, failing: failingJobs, running: running.length };
  const local = connection?.kind === "local";
  const unreadCount = member ? 0 : Math.max(0, Math.floor(Number(unread) || 0));
  const candidates = sources
    .filter((src) => !src.member)
    .flatMap((src) => src.groups.upcoming.map((job) => ({ job, src })));
  const nextRows = candidates
    .sort((a, b) => a.job.nextAt - b.job.nextAt)
    .slice(0, MAX_NEXT_ROWS)
    .map(({ job, src }) => ({
      id: `${src.id}/${job.profile ?? ""}/${job.job_id ?? ""}`,
      title: clip(job.title || job.job_id),
      label: clip(profileLabel(job.profile ?? "")),
      at: new Date(job.nextAt * 1000).toISOString(),
      source: several ? clip(src.name, 40) : null,
      fold: src.folds?.[job.profile] ?? null,
      accent: src.accents?.[job.profile] ?? null,
      deeplink: job.profile ? { kind: "settings", profile: job.profile, id: "schedules", connection_id: src.id } : null,
    }));
  return {
    v: TRAY_SNAPSHOT_VERSION,
    state: unsupported && !counts.needs && !counts.failing && !counts.running ? "online" : trayState({ link, ...counts }),
    counts,
    member: Boolean(member),
    unread: unreadCount,
    update: update ? { version: update.version == null ? null : clip(update.version, MAX_VERSION), busy: Boolean(update.busy) } : null,
    needs: {
      total: needs.length,
      approvals,
      questions: needs.length - approvals,
      rows: needsRows(needs),
    },
    failing: {
      jobs: failingJobs,
      profileCount: failingProfiles.length,
      profiles: failingNames.slice(0, 2),
    },
    running: {
      count: counts.running,
      rows: runningRows(running),
    },
    next: nextRows.length ? { rows: nextRows, total: candidates.length } : null,
    offline: rawLink === "offline"
      ? { local, canStart: local && daemon?.state === "stopped", absent: local && (daemon?.state === "absent" || daemon?.state === "unsupported") }
      : null,
  };
}
