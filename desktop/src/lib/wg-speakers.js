const PEER_PALETTE = [
  "#1877f2", "#e0245e", "#7a3ec3", "#0a84ff", "#ff6b35",
  "#30d158", "#bf5af2", "#ff9f0a", "#5e5ce6", "#64d2ff",
];

export function paletteFor(seed) {
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return PEER_PALETTE[Math.abs(h) % PEER_PALETTE.length];
}

export function buildSpeakerIndex(profiles, peers, members) {
  const memberByPk = new Map();
  const memberBioByPk = new Map();
  for (const m of members ?? []) {
    if (!m?.pubkey) continue;
    memberByPk.set(m.pubkey, m);
    const bio = (m.bio || "").trim();
    if (bio) memberBioByPk.set(m.pubkey, bio);
  }
  const profileByPk = new Map();
  for (const p of profiles ?? []) {
    if (p?.pubkey_b64) profileByPk.set(p.pubkey_b64, p);
  }
  const peerByPk = new Map();
  for (const p of peers ?? []) {
    if (p?.pubkey) peerByPk.set(p.pubkey, p);
  }
  return { memberByPk, memberBioByPk, profileByPk, peerByPk };
}

export function speakerFromIndex(index, msg) {
  const pubkey = msg.from_pubkey || "";
  const memberBio = pubkey ? (index.memberBioByPk.get(pubkey) ?? null) : null;
  if (pubkey) {
    const matchProfile = index.profileByPk.get(pubkey);
    if (matchProfile) {
      const localBio =
        (matchProfile.bio || matchProfile.public_bio || "").trim() || null;
      return {
        name: matchProfile.name,
        accent: matchProfile.accent ?? paletteFor(matchProfile.name),
        bio: memberBio || localBio,
      };
    }
    const peer = index.peerByPk.get(pubkey);
    if (peer) return { name: peer.id, accent: paletteFor(peer.id), bio: memberBio };
    const member = index.memberByPk.get(pubkey);
    if (member?.bio) {
      return { name: member.bio, accent: paletteFor(member.bio), bio: null };
    }
  }
  const handle = String(msg.from || "").replace(/^@/, "");
  return { name: handle, accent: paletteFor(handle), bio: null };
}
