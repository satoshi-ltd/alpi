export const ACCESS_SHOWN = 3;
export const ALL_PROFILES = "All profiles";

export function connectionAccess(row, profiles = null, limit = ACCESS_SHOWN) {
  const scope = row?.role === "admin" ? [] : (row?.profile_scope ?? []).filter(Boolean);
  if (!scope.length) return { all: true, entries: [], shown: [], more: [], names: [] };
  const loaded = Array.isArray(profiles);
  const byName = new Map((profiles ?? []).map((p) => [p.name, p]));
  const entries = scope.map((name) => {
    const profile = byName.get(name);
    return { name, known: loaded ? !!profile : null, accent: profile?.accent ?? null, shape: profile?.shape ?? null };
  });
  return { all: false, entries, shown: entries.slice(0, limit), more: entries.slice(limit).map((e) => e.name), names: scope };
}

export function accessSpoken(access, label = (name) => name) {
  if (access.all) return ALL_PROFILES;
  const gone = new Set(access.entries.filter((e) => e.known === false).map((e) => e.name));
  return access.names.map((name) => (gone.has(name) ? `${label(name)} (removed)` : label(name))).join(", ");
}
