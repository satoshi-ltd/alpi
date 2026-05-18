// Sidebar order — pinned profiles + workgroups first (in pin-order),
// then unpinned profiles by completeness/recency. Shared between Sidebar
// render and ⌘1-9 jump shortcuts so the keys match what the user sees.

function recency(profile) {
  const ls = profile.latest_session;
  return ls?.updated_at ?? ls?.started_at ?? ls?.mtime ?? 0;
}

export function orderedSidebarProfiles(profiles, pinnedNames = []) {
  const pinnedSet = new Set(pinnedNames);
  const pinned = pinnedNames
    .map((name) => profiles.find((p) => p.name === name))
    .filter(Boolean);
  const rest = profiles.filter((p) => !pinnedSet.has(p.name));
  rest.sort((a, b) => {
    const aIncomplete = !a.model ? 1 : 0;
    const bIncomplete = !b.model ? 1 : 0;
    if (aIncomplete !== bIncomplete) return aIncomplete - bIncomplete;
    return recency(b) - recency(a);
  });
  return [...pinned, ...rest];
}

// Items eligible for ⌘1-9 jump: pinned profiles + pinned workgroups (in
// pin-order, profiles before workgroups), then unpinned profiles by
// recency. Returns a uniform shape: { kind: "profile"|"workgroup", target }.
export function orderedJumpTargets({
  profiles,
  workgroups,
  pinnedProfiles = [],
  pinnedWorkgroups = [],
}) {
  const pinnedProfileSet = new Set(pinnedProfiles);
  const pinnedWgSet = new Set(pinnedWorkgroups);

  const pinnedProfileItems = pinnedProfiles
    .map((name) => profiles.find((p) => p.name === name))
    .filter(Boolean)
    .map((p) => ({ kind: "profile", target: p }));

  const pinnedWgItems = pinnedWorkgroups
    .map((key) =>
      workgroups.find((w) => `${w.profile}/${w.id}` === key),
    )
    .filter(Boolean)
    .map((w) => ({ kind: "workgroup", target: w }));

  const restProfiles = profiles
    .filter((p) => !pinnedProfileSet.has(p.name))
    .sort((a, b) => {
      const aIncomplete = !a.model ? 1 : 0;
      const bIncomplete = !b.model ? 1 : 0;
      if (aIncomplete !== bIncomplete) return aIncomplete - bIncomplete;
      return recency(b) - recency(a);
    })
    .map((p) => ({ kind: "profile", target: p }));

  return [...pinnedProfileItems, ...pinnedWgItems, ...restProfiles];
}
