export function canDraftIdentity(profile) {
  return !!profile?.model;
}

// host.identity.draft synthesizes from AGENT.md through the profile's model; without one the daemon answers -32010.
export async function draftIdentity(call, profileId) {
  const result = await call('host.identity.draft', { profile: profileId });
  return String(result?.bio ?? '').trim();
}

export function saveIdentity(call, profileId, text) {
  return call('host.config.set_field', { profile: profileId, key: 'public_bio', value: text });
}
