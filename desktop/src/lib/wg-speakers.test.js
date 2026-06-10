import { describe, it, expect } from "vitest";
import { buildSpeakerIndex, paletteFor, speakerFromIndex } from "./wg-speakers.js";

const profiles = [
  { name: "doc", pubkey_b64: "pk-doc", accent: "#123456", bio: "local doc bio" },
  { name: "muse", pubkey_b64: "pk-muse", public_bio: "muse public" },
];
const peers = [{ id: "remote-peer", pubkey: "pk-peer" }];
const members = [
  { pubkey: "pk-doc", bio: "member doc bio" },
  { pubkey: "pk-only-member", bio: "Brings outside evidence" },
  { pubkey: "pk-empty-bio", bio: "  " },
];

const index = buildSpeakerIndex(profiles, peers, members);

describe("speakerFromIndex", () => {
  it("matches a local profile and prefers the member bio over the local one", () => {
    const s = speakerFromIndex(index, { from_pubkey: "pk-doc" });
    expect(s).toEqual({ name: "doc", accent: "#123456", bio: "member doc bio" });
  });

  it("falls back to the profile's public_bio when no member bio exists", () => {
    const s = speakerFromIndex(index, { from_pubkey: "pk-muse" });
    expect(s.name).toBe("muse");
    expect(s.bio).toBe("muse public");
    expect(s.accent).toBe(paletteFor("muse"));
  });

  it("matches a known peer by pubkey", () => {
    const s = speakerFromIndex(index, { from_pubkey: "pk-peer" });
    expect(s).toEqual({
      name: "remote-peer",
      accent: paletteFor("remote-peer"),
      bio: null,
    });
  });

  it("uses the member bio as display name when only the member is known", () => {
    const s = speakerFromIndex(index, { from_pubkey: "pk-only-member" });
    expect(s.name).toBe("Brings outside evidence");
    expect(s.bio).toBeNull();
  });

  it("falls back to the @handle for unknown pubkeys", () => {
    const s = speakerFromIndex(index, { from_pubkey: "pk-???", from: "@ghost" });
    expect(s).toEqual({ name: "ghost", accent: paletteFor("ghost"), bio: null });
  });

  it("a whitespace-only member bio is still used as name (legacy resolveSpeaker parity)", () => {
    const s = speakerFromIndex(index, { from_pubkey: "pk-empty-bio", from: "@x" });
    expect(s.name).toBe("  ");
    expect(s.bio).toBeNull();
  });

  it("paletteFor is deterministic", () => {
    expect(paletteFor("abc")).toBe(paletteFor("abc"));
  });
});
