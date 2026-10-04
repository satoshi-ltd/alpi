export const DEFAULT_PROFILE_NAME = "default";

export function isDefaultProfile(profile) {
  return !!profile && (profile.is_default === true || profile.name === DEFAULT_PROFILE_NAME);
}

export function splitDefaultProfile(list, profileOf = (entry) => entry) {
  const entries = Array.isArray(list) ? list : [];
  const front = entries.find((entry) => isDefaultProfile(profileOf(entry))) ?? null;
  return { front, rest: front ? entries.filter((entry) => entry !== front) : entries };
}

export function withoutDefaultPin(names) {
  return (Array.isArray(names) ? names : []).filter((name) => name !== DEFAULT_PROFILE_NAME);
}
