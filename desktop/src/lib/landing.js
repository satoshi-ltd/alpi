export const LANDING_VIEW = { kind: "landing" };

export function firstRosterProfile(jumpTargets) {
  return (jumpTargets ?? []).find((item) => item.kind === "profile")?.target ?? null;
}

export function profileLandingView(profile) {
  const latest = profile?.latest_session;
  return {
    kind: "profile",
    profile: profile.name,
    sessionId: latest?.kind === "chat" ? latest.id : null,
  };
}

export function newSessionProfile({ view, profiles, lastSeen = null, firstProfile = null }) {
  const served = (name) => !!name && (profiles ?? []).some((p) => p.name === name);
  if (view?.kind === "profile" && served(view.profile)) return view.profile;
  if (served(lastSeen)) return lastSeen;
  return firstProfile?.name ?? null;
}

export function viewLeavingSettings({ target, previous, profiles = [], workgroups = [] }) {
  const profileNamed = (name) => profiles.find((p) => p.name === name) ?? null;
  const workgroupOf = (id, profile = null) =>
    workgroups.find((w) => w.id === id && (profile == null || w.profile === profile)) ?? null;
  if (target?.kind === "profile" && target.id) {
    const profile = profileNamed(target.id);
    return profile ? profileLandingView(profile) : LANDING_VIEW;
  }
  if (target?.kind === "workgroup" && target.id) {
    const wg = workgroupOf(target.id);
    if (wg) return { kind: "workgroup", profile: wg.profile, id: wg.id };
  }
  if (!previous || previous.kind === "settings" || previous.kind === "landing") return LANDING_VIEW;
  if (previous.kind === "profile" && !profileNamed(previous.profile)) return LANDING_VIEW;
  if (previous.kind === "workgroup" && !workgroupOf(previous.id, previous.profile)) return LANDING_VIEW;
  return previous;
}

export function swapPreviousView(saved, from, to, current) {
  return { saved: { ...saved, [from]: current }, previous: saved[to] ?? LANDING_VIEW };
}
