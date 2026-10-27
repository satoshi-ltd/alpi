import { groupActivity } from "../../../common/activityGroups.mjs";
import { trayState, MAX_NEEDS_ROWS } from "../tray/trayModel.js";
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
  const first = groups.running[0];
  const local = connection?.kind === "local";
  const unreadCount = member ? 0 : Math.max(0, Math.floor(Number(unread) || 0));
  const upcoming = !member && online && activitySupported && activity != null ? groups.upcoming[0] : null;
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
      first: first ? { label: clip(profileLabel(first.profile ?? "")), title: clip(first.title || first.name) } : null,
    },
    next: upcoming ? { title: clip(upcoming.title || upcoming.job_id), at: new Date(upcoming.nextAt * 1000).toISOString() } : null,
    offline: rawLink === "offline"
      ? { local, canStart: local && daemon?.state === "stopped", absent: local && (daemon?.state === "absent" || daemon?.state === "unsupported") }
      : null,
  };
}
