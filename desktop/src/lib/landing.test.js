import { describe, expect, it } from "vitest";
import { orderedJumpTargets } from "./profile-order.js";
import { LANDING_VIEW, firstRosterProfile, newSessionProfile, profileLandingView, swapPreviousView, viewLeavingSettings } from "./landing.js";

const alpi = { name: "default", is_default: true, model: "m", latest_session: { kind: "chat", id: "s-alpi", updated_at: 1 } };
const doc = { name: "doc", model: "m", latest_session: { kind: "chat", id: "s-doc", updated_at: 9 } };
const abby = { name: "abby", model: "m", latest_session: { kind: "cron", id: "s-cron", updated_at: 5 } };
const crew = { profile: "doc", id: "crew", mtime: 99 };

const targets = (profiles, pinned = {}) =>
  orderedJumpTargets({
    profiles,
    workgroups: [crew],
    pinnedProfiles: pinned.profiles ?? [],
    pinnedWorkgroups: pinned.workgroups ?? [],
  });

describe("firstRosterProfile", () => {
  it("is alpi whenever the daemon serves the default profile", () => {
    expect(firstRosterProfile(targets([doc, abby, alpi], { profiles: ["abby"] }))).toBe(alpi);
  });

  it("is the first profile row otherwise, skipping a pinned workgroup above it", () => {
    expect(firstRosterProfile(targets([abby, doc], { workgroups: ["doc/crew"] }))).toBe(doc);
  });

  it("is null with no profiles", () => {
    expect(firstRosterProfile(targets([]))).toBeNull();
    expect(firstRosterProfile(undefined)).toBeNull();
  });
});

describe("profileLandingView", () => {
  it("opens the profile on its latest chat, as a click on the row does", () => {
    expect(profileLandingView(doc)).toEqual({ kind: "profile", profile: "doc", sessionId: "s-doc" });
  });

  it("opens a new thread when the latest session is not a chat", () => {
    expect(profileLandingView(abby)).toEqual({ kind: "profile", profile: "abby", sessionId: null });
  });
});

describe("newSessionProfile", () => {
  const profiles = [alpi, doc, abby];

  it("keeps the open profile", () => {
    expect(newSessionProfile({ view: { kind: "profile", profile: "abby", sessionId: "x" }, profiles, lastSeen: "doc", firstProfile: alpi })).toBe("abby");
  });

  it("never targets a profile the active connection does not serve, even the open one", () => {
    const view = { kind: "profile", profile: "mirai", sessionId: "x" };
    expect(newSessionProfile({ view, profiles, lastSeen: "mirai", firstProfile: alpi })).toBe("default");
    expect(newSessionProfile({ view, profiles: [], lastSeen: "mirai", firstProfile: null })).toBeNull();
  });

  it("uses the last profile seen from a workgroup, the workgroups list, Settings or the landing", () => {
    for (const view of [{ kind: "workgroup", profile: "doc", id: "crew" }, { kind: "workgroups" }, { kind: "settings" }, LANDING_VIEW]) {
      expect(newSessionProfile({ view, profiles, lastSeen: "doc", firstProfile: alpi })).toBe("doc");
    }
  });

  it("falls back to the first roster row when the last profile seen is gone or unknown", () => {
    expect(newSessionProfile({ view: { kind: "settings" }, profiles, lastSeen: "deleted", firstProfile: alpi })).toBe("default");
    expect(newSessionProfile({ view: { kind: "workgroup", profile: "doc", id: "crew" }, profiles, firstProfile: alpi })).toBe("default");
  });

  it("has no target with no profiles, so a workgroup never becomes one", () => {
    expect(newSessionProfile({ view: { kind: "workgroup", profile: "doc", id: "crew" }, profiles: [], lastSeen: "doc", firstProfile: null })).toBeNull();
  });
});

describe("viewLeavingSettings", () => {
  const profiles = [alpi, doc];
  const workgroups = [crew];

  it("opens the Settings profile on its latest chat when the connection serves it", () => {
    expect(viewLeavingSettings({ target: { kind: "profile", id: "doc" }, profiles, workgroups })).toEqual(profileLandingView(doc));
  });

  it("lands on the roster when the Settings profile belongs to another connection", () => {
    expect(viewLeavingSettings({ target: { kind: "profile", id: "mirai" }, previous: { kind: "profile", profile: "doc" }, profiles, workgroups })).toBe(LANDING_VIEW);
  });

  it("opens the Settings workgroup when it still exists", () => {
    expect(viewLeavingSettings({ target: { kind: "workgroup", id: "crew" }, profiles, workgroups })).toEqual({ kind: "workgroup", profile: "doc", id: "crew" });
  });

  it("returns to the previous view only when the active connection still has it", () => {
    const previous = { kind: "profile", profile: "doc", sessionId: "s-doc" };
    expect(viewLeavingSettings({ target: { kind: "connections" }, previous, profiles, workgroups })).toBe(previous);
    expect(viewLeavingSettings({ target: { kind: "connections" }, previous: { kind: "profile", profile: "mirai" }, profiles, workgroups })).toBe(LANDING_VIEW);
    expect(viewLeavingSettings({ target: { kind: "connections" }, previous: { kind: "workgroup", profile: "x", id: "gone" }, profiles, workgroups })).toBe(LANDING_VIEW);
    expect(viewLeavingSettings({ target: null, previous: { kind: "workgroups" }, profiles, workgroups })).toEqual({ kind: "workgroups" });
    expect(viewLeavingSettings({ target: null, previous: null, profiles, workgroups })).toBe(LANDING_VIEW);
  });
});

describe("previous view per connection", () => {
  it("brings back a connection's own previous view after a round trip and never another connection's", () => {
    const doc = { kind: "profile", profile: "doc", sessionId: "s-doc" };
    const out = swapPreviousView({}, "local", "remote", doc);
    expect(out.previous).toEqual(LANDING_VIEW);
    const back = swapPreviousView(out.saved, "remote", "local", out.previous);
    expect(back.previous).toEqual(doc);
  });
});
