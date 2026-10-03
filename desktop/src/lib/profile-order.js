import { splitDefaultProfile, withoutDefaultPin } from "../../../common/rosterOrder.mjs";

function recency(profile) {
  const ls = profile.latest_session;
  return ls?.updated_at ?? ls?.started_at ?? ls?.mtime ?? 0;
}

export function compareProfiles(a, b) {
  const aPaused = a.paused ? 1 : 0;
  const bPaused = b.paused ? 1 : 0;
  if (aPaused !== bPaused) return aPaused - bPaused;
  const aIncomplete = !a.model ? 1 : 0;
  const bIncomplete = !b.model ? 1 : 0;
  if (aIncomplete !== bIncomplete) return aIncomplete - bIncomplete;
  return recency(b) - recency(a);
}

export function orderedSidebarProfiles(profiles, pinnedNames = []) {
  const { front, rest: others } = splitDefaultProfile(profiles);
  const pins = withoutDefaultPin(pinnedNames);
  const pinnedSet = new Set(pins);
  const pinned = pins
    .map((name) => others.find((p) => p.name === name))
    .filter(Boolean);
  const rest = others.filter((p) => !pinnedSet.has(p.name));
  rest.sort(compareProfiles);
  return [...(front ? [front] : []), ...pinned, ...rest];
}

export function orderPinnedItems(pinnedProfiles = [], pinnedWorkgroups = []) {
  const items = [
    ...pinnedProfiles.map((p) => ({
      kind: "profile",
      item: p,
      ts: recency(p),
      bad: p.paused || !p.model ? 1 : 0,
    })),
    ...pinnedWorkgroups.map((w) => ({
      kind: "workgroup",
      item: w,
      ts: w.mtime ?? 0,
      bad: w.paused ? 1 : 0,
    })),
  ];
  items.sort((a, b) => (a.bad !== b.bad ? a.bad - b.bad : b.ts - a.ts));
  return items;
}

export function orderedJumpTargets({
  profiles,
  workgroups,
  pinnedProfiles = [],
  pinnedWorkgroups = [],
}) {
  const { front, rest: others } = splitDefaultProfile(profiles);
  const pins = withoutDefaultPin(pinnedProfiles);
  const pinnedProfileSet = new Set(pins);

  const frontItems = front ? [{ kind: "profile", target: front }] : [];

  const pinnedItems = orderPinnedItems(
    pins.map((name) => others.find((p) => p.name === name)).filter(Boolean),
    pinnedWorkgroups.map((key) => workgroups.find((w) => `${w.profile}/${w.id}` === key)).filter(Boolean),
  ).map(({ kind, item }) => ({ kind, target: item }));

  const restProfiles = others
    .filter((p) => !pinnedProfileSet.has(p.name))
    .sort(compareProfiles)
    .map((p) => ({ kind: "profile", target: p }));

  return [...frontItems, ...pinnedItems, ...restProfiles];
}
