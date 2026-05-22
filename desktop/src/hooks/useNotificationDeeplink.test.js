import { describe, it, expect } from "vitest";

import { resolveDeeplink } from "./useNotificationDeeplink.js";

describe("resolveDeeplink", () => {
  it("opens the chat with a specific session when kind=chat carries id", () => {
    expect(resolveDeeplink({ kind: "chat", profile: "abby", id: "sess-1" })).toEqual({
      view: { kind: "profile", profile: "abby", sessionId: "sess-1" },
    });
  });

  it("opens the latest chat in the profile when kind=chat has no id", () => {
    expect(resolveDeeplink({ kind: "chat", profile: "abby" })).toEqual({
      view: { kind: "profile", profile: "abby", sessionId: null },
    });
  });

  it("opens the profile's latest chat when kind=profile", () => {
    expect(resolveDeeplink({ kind: "profile", profile: "abby" })).toEqual({
      view: { kind: "profile", profile: "abby", sessionId: null },
    });
  });

  it("opens a workgroup view when both profile and id are present", () => {
    expect(resolveDeeplink({ kind: "workgroup", profile: "vera", id: "wg-1" })).toEqual({
      view: { kind: "workgroup", profile: "vera", id: "wg-1" },
    });
  });

  it("opens settings with a profile target when provided", () => {
    expect(resolveDeeplink({ kind: "settings", profile: "abby" })).toEqual({
      settingsTarget: { kind: "profile", id: "abby" },
      view: { kind: "settings" },
    });
  });

  it("opens settings without a target when no profile attached", () => {
    expect(resolveDeeplink({ kind: "settings" })).toEqual({
      settingsTarget: null,
      view: { kind: "settings" },
    });
  });

  it("returns null for malformed payloads so the consumer skips dispatch", () => {
    expect(resolveDeeplink(null)).toBeNull();
    expect(resolveDeeplink(undefined)).toBeNull();
    expect(resolveDeeplink({})).toBeNull();
    expect(resolveDeeplink({ kind: "chat" })).toBeNull();
    expect(resolveDeeplink({ kind: "profile" })).toBeNull();
    expect(resolveDeeplink({ kind: "workgroup", profile: "vera" })).toBeNull();
    expect(resolveDeeplink({ kind: "unknown", profile: "abby" })).toBeNull();
  });
});
