import { describe, expect, it } from "vitest";

import { belongsToChat, splitInline } from "./inlineRequests.js";

describe("belongsToChat", () => {
  const scope = { profile: "doc", sessionIds: ["s1", null], live: false };

  it("matches the open chat's profile and session", () => {
    expect(belongsToChat({ profile: "doc", session_id: "s1" }, scope)).toBe(true);
    expect(belongsToChat({ profile: "doc", session_id: "s2" }, scope)).toBe(false);
    expect(belongsToChat({ profile: "other", session_id: "s1" }, scope)).toBe(false);
  });

  it("inlines a session-less request only while the open chat has a live turn", () => {
    expect(belongsToChat({ profile: "doc", session_id: null }, scope)).toBe(false);
    expect(belongsToChat({ profile: "doc" }, { profile: "doc", sessionIds: ["s1"], live: true })).toBe(true);
    expect(belongsToChat({ profile: "doc" }, { profile: "doc", sessionIds: [null], live: false })).toBe(false);
  });

  it("never claims a request when no chat is open", () => {
    expect(belongsToChat({ profile: "doc", session_id: "s1" }, { profile: null, sessionIds: ["s1"] })).toBe(false);
  });
});

describe("splitInline", () => {
  it("keeps queue order in both halves", () => {
    const q = [
      { request_id: "a", profile: "doc", session_id: "s1" },
      { request_id: "b", profile: "other", session_id: "x" },
      { request_id: "c", profile: "doc", session_id: "s1" },
    ];
    const { inline, modal } = splitInline(q, { profile: "doc", sessionIds: ["s1"] });
    expect(inline.map((r) => r.request_id)).toEqual(["a", "c"]);
    expect(modal.map((r) => r.request_id)).toEqual(["b"]);
  });
});
