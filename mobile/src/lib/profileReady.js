export function profileHasProviders(profile) {
  if (!profile) return false;
  // Daemon-precomputed flag (host.profile.summaries) — avoids host.profile.detail roundtrip for empty-state branching.
  if (typeof profile.has_any_provider === 'boolean') return profile.has_any_provider;
  const hasOllama = (profile.provider_ollama?.length ?? 0) > 0;
  const hasCloudModels = (profile.models?.length ?? 0) > 0;
  const hasCloudKeys = (profile.provider_keys?.length ?? 0) > 0;
  return hasOllama || hasCloudModels || hasCloudKeys;
}

export function profileReadyToChat(profile) {
  return !!profile?.model;
}

export function profileEmptyState(profile) {
  if (!profile) return 'needs-provider';
  if (profile.model) return 'ready';
  return profileHasProviders(profile) ? 'needs-model' : 'needs-provider';
}
