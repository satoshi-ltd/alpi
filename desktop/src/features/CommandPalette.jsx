import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Palette } from "../primitives/Panels.jsx";
import { Diamond, DiamondStack, Icon } from "../primitives/index.js";
import { I } from "../primitives/icons.jsx";
import { profileLabel } from "../lib/profile-display.js";
import { displaySessionTitle } from "../lib/session-titles.js";
import { relativeTime } from "../lib/time.js";
import { ICON_ROLES } from "../../../common/iconRoles.mjs";

const SESSION_FETCH_LIMIT = 12;
const SESSION_ROWS = 8;

const GLYPH_BY_PREFIX = {
  "view:settings": () => <Icon name={ICON_ROLES.settings} />,
  "view:find": () => <I.Search />,
  "view:notifications": () => <Icon name={ICON_ROLES.notifications} />,
  "view:shortcuts": () => <Icon name="more" />,
  "view:activity": () => <Icon name={ICON_ROLES.activity} />,
  "chat:find": () => <I.Search />,
  "chat:refresh": () => <I.Refresh />,
  "chat:read-aloud": () => <I.Volume />,
  "profile:sessions": () => <I.Archive />,
  "profile:pause": () => <I.Pause />,
  "workgroup:tasks": () => <I.Check />,
  "workgroup:pause": () => <I.Pause />,
  "workgroup:refresh": () => <I.Refresh />,
  "profile:tools": () => <I.Wrench />,
  "profile:skills": () => <I.Blocks />,
  "profile:memory": () => <I.Cpu />,
  "create:chat": () => <I.Plus />,
  "create:profile": () => <I.Plus />,
  "create:workgroup": () => <I.Plus />,
  "pref:theme": () => <I.Sun />,
};

function resolveGlyph(cmd) {
  const make = GLYPH_BY_PREFIX[cmd.id];
  return make ? make() : <I.ChevRight />;
}

export const SESSION_CACHE_TTL_MS = 30000;
const SESSION_CONCURRENCY = 4;
const sessionCache = new Map();

export function _resetSessionCache() {
  sessionCache.clear();
}

async function mapBounded(items, limit, fn) {
  const out = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const i = next++;
      out[i] = await fn(items[i]);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return out;
}

function recentChats(lists) {
  const seen = new Set();
  return lists
    .flat()
    .filter((s) => {
      if (s?.kind !== "chat" || !s.first_user) return false;
      const id = `${s.profile}/${s.id}`;
      if (seen.has(id)) return false;
      seen.add(id);
      return true;
    })
    .sort((a, b) => (b.updated_at || b.mtime || 0) - (a.updated_at || a.mtime || 0))
    .slice(0, SESSION_FETCH_LIMIT);
}

export function loadRecentSessions(connectionId, profileNames, now = Date.now()) {
  const key = `${connectionId ?? ""}|${profileNames.join(",")}`;
  const hit = sessionCache.get(key);
  if (hit && now - hit.at < SESSION_CACHE_TTL_MS) return hit.promise;
  const promise = mapBounded(profileNames, SESSION_CONCURRENCY, (profile) =>
    invoke("sessions", { profile, limit: SESSION_FETCH_LIMIT, connectionId: connectionId ?? null })
      .then((rows) => (Array.isArray(rows) ? rows : []))
      .catch(() => []),
  ).then(recentChats);
  sessionCache.set(key, { at: now, promise });
  promise.catch(() => sessionCache.delete(key));
  return promise;
}

export function useRecentSessions(open, connectionId, profileNames = []) {
  const [state, setState] = useState({ key: null, rows: [] });
  const namesKey = profileNames.join(",");
  const key = `${connectionId ?? ""}|${namesKey}`;
  useEffect(() => {
    if (!open || !namesKey) return undefined;
    let cancelled = false;
    loadRecentSessions(connectionId, namesKey.split(",")).then((rows) => {
      if (!cancelled) setState({ key, rows });
    });
    return () => { cancelled = true; };
  }, [open, connectionId, namesKey, key]);
  return open && state.key === key ? state.rows : EMPTY_ROWS;
}

const EMPTY_ROWS = [];

export function entityGroups({
  profiles = [],
  workgroups = [],
  sessions = [],
  jumpHints = {},
  connectionId = null,
  onOpenProfile,
  onOpenWorkgroup,
  onOpenSession,
  now = Date.now(),
}) {
  const hint = (n) => (n ? `⌘${n}` : undefined);
  return [
    {
      label: "Profiles",
      searchOnly: true,
      items: profiles.map((p) => ({
        id: `profile:${p.name}`,
        label: profileLabel(p.name),
        keywords: [p.name, p.bio || ""].filter(Boolean),
        sub: "profile",
        shortcut: hint(jumpHints[`profile:${p.name}`]),
        glyph: <Diamond color={p.accent || undefined} />,
        onSelect: onOpenProfile ? () => onOpenProfile(p) : undefined,
      })),
    },
    {
      label: "Workgroups",
      searchOnly: true,
      items: workgroups.map((w) => ({
        id: `workgroup:${w.profile}/${w.id}`,
        label: w.name ?? w.id,
        keywords: [String(w.id ?? ""), w.profile].filter(Boolean),
        sub: `#${profileLabel(w.profile)}`,
        shortcut: hint(jumpHints[`workgroup:${w.profile}/${w.id}`]),
        glyph: <DiamondStack />,
        onSelect: onOpenWorkgroup ? () => onOpenWorkgroup(w) : undefined,
      })),
    },
    {
      label: "Sessions",
      searchOnly: true,
      limit: SESSION_ROWS,
      items: sessions.map((s) => {
        const ts = s.updated_at || s.started_at || s.mtime || 0;
        return {
          id: `session:${s.profile}/${s.id}`,
          label: displaySessionTitle(s, { connectionId, profile: s.profile, max: 80 }),
          keywords: [s.first_user || ""],
          sub: [`@${profileLabel(s.profile)}`, ts ? relativeTime(ts, now) : null].filter(Boolean).join(" · "),
          glyph: <Icon name="clock" />,
          onSelect: onOpenSession ? () => onOpenSession(s.profile, s.id) : undefined,
        };
      }),
    },
  ];
}

export default function CommandPalette({
  open,
  onClose,
  commands,
  profiles = [],
  workgroups = [],
  jumpHints = {},
  connectionId = null,
  onOpenProfile,
  onOpenWorkgroup,
  onOpenSession,
}) {
  const profileNames = useMemo(() => profiles.map((p) => p.name), [profiles]);
  const sessions = useRecentSessions(open, connectionId, profileNames);
  const groups = useMemo(() => {
    const byGroup = new Map();
    commands.forEach((c) => {
      if (!byGroup.has(c.group)) byGroup.set(c.group, []);
      byGroup.get(c.group).push({
        id: c.id,
        label: c.label,
        shortcut: c.hint,
        glyph: resolveGlyph(c),
        onSelect: c.action,
      });
    });
    const commandGroups = Array.from(byGroup.entries()).map(([label, items]) => ({
      label,
      items,
    }));
    return [
      ...entityGroups({
        profiles,
        workgroups,
        sessions,
        jumpHints,
        connectionId,
        onOpenProfile,
        onOpenWorkgroup,
        onOpenSession,
      }),
      ...commandGroups,
    ];
  }, [commands, profiles, workgroups, sessions, jumpHints, connectionId, onOpenProfile, onOpenWorkgroup, onOpenSession]);

  return <Palette open={open} onClose={onClose} groups={groups} />;
}
