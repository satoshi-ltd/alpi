import { describe, expect, it } from "vitest";
import { canRefreshProfileThread, profileManagementAllowed,
  connectionFailureMessage,
  isChatSessionData,
  profileSurfaceKey,
  settingsTargetAfterExit,
  settingsTargetForChatView,
} from "./App.jsx";

describe("connectionFailureMessage", () => {
  it("distinguishes a disabled connection from a rejected token", () => {
    expect(connectionFailureMessage({ name: "office", status: "disabled" })).toBe(
      "office — connection disabled by host. Ask an admin to enable it in Settings → Connections.",
    );
    expect(connectionFailureMessage({ name: "office", status: "auth-failed" })).toBe(
      "office — token rejected. Re-pair device from Settings.",
    );
  });
});

describe("isChatSessionData", () => {
  it("trusts the daemon kind when present", () => {
    expect(isChatSessionData({ kind: "chat", turns: [] })).toBe(true);
    expect(isChatSessionData({ kind: "empty", turns: [] })).toBe(true);
    expect(isChatSessionData({ kind: "workgroup", turns: [{ user: "hola" }] })).toBe(false);
    expect(isChatSessionData({ kind: "scheduled", turns: [] })).toBe(false);
  });

  it("never classifies an offset slice by its first visible turn", () => {
    expect(
      isChatSessionData({ turnsOffset: 40, turns: [{ user: "[workgroup-poller] tick" }] }),
    ).toBe(true);
  });

  it("keeps the heuristic for full reads without kind", () => {
    expect(isChatSessionData({ turns: [{ user: "[workgroup-poller] tick" }] })).toBe(false);
    expect(isChatSessionData({ turns: [{ user: "[SCHEDULED: daily] go" }] })).toBe(false);
    expect(isChatSessionData({ turns: [{ user: "hola" }] })).toBe(true);
    expect(isChatSessionData({ turns: [] })).toBe(true);
  });
});

describe("settingsTargetAfterExit", () => {
  it("restores the previous settings target after leaving connections", () => {
    const previous = { kind: "profile", id: "default" };

    expect(settingsTargetAfterExit({ kind: "connections" }, previous)).toEqual(previous);
    expect(settingsTargetAfterExit({ kind: "connections" }, null)).toEqual({
      kind: "profile",
      id: null,
    });
  });

  it("preserves normal settings targets", () => {
    const target = { kind: "profile", id: "atlas" };

    expect(settingsTargetAfterExit(target, null)).toBe(target);
  });
});

describe("settingsTargetForChatView", () => {
  it("derives settings from the current chat instead of the previous settings panel", () => {
    expect(settingsTargetForChatView({ kind: "profile", profile: "atlas" })).toEqual({
      kind: "profile",
      id: "atlas",
    });
    expect(settingsTargetForChatView({ kind: "workgroup", id: "build" })).toEqual({
      kind: "workgroup",
      id: "build",
    });
    expect(settingsTargetForChatView({ kind: "empty" }, "default")).toEqual({
      kind: "profile",
      id: "default",
    });
  });
});


describe("canRefreshProfileThread", () => {
  it("shows refresh for an open session even before any turn loads (failed/slow fetch must stay retryable)", () => {
    expect(canRefreshProfileThread({ kind: "profile", sessionId: "s1" }, null)).toBe(true);
  });

  it("hides refresh on a profile with no session and no turns", () => {
    expect(canRefreshProfileThread({ kind: "profile", sessionId: null }, { turns: [] })).toBe(false);
  });

  it("shows refresh when turns are loaded and always for workgroups", () => {
    expect(canRefreshProfileThread({ kind: "profile", sessionId: null }, { turns: [{}] })).toBe(true);
    expect(canRefreshProfileThread({ kind: "workgroup" }, null)).toBe(true);
  });
});


describe("profileManagementAllowed", () => {
  it("members lose skills/memory/tools/schedule surfaces; admin and pre-probe keep them", () => {
    expect(profileManagementAllowed("member")).toBe(false);
    expect(profileManagementAllowed("admin")).toBe(true);
    expect(profileManagementAllowed(null)).toBe(true);
    expect(profileManagementAllowed(undefined)).toBe(true);
  });
});

describe("profileSurfaceKey", () => {
  const surfaces = ["tools", "skills", "memory", "schedule"];

  it("keeps the four sibling modals distinct on the same connection and profile", () => {
    const keys = surfaces.map((s) => profileSurfaceKey(s, "local", "lens"));
    expect(new Set(keys).size).toBe(4);
  });

  it("stays distinct when no profile is selected", () => {
    const keys = surfaces.map((s) => profileSurfaceKey(s, "local", null));
    expect(new Set(keys).size).toBe(4);
    expect(keys).not.toContain("local:");
  });

  it("still remounts when the connection or the profile changes", () => {
    expect(profileSurfaceKey("tools", "local", "lens")).not.toBe(
      profileSurfaceKey("tools", "office", "lens"),
    );
    expect(profileSurfaceKey("tools", "local", "lens")).not.toBe(
      profileSurfaceKey("tools", "local", "lingua"),
    );
    expect(profileSurfaceKey("tools", "local", "lens")).toBe(
      profileSurfaceKey("tools", "local", "lens"),
    );
  });
});
