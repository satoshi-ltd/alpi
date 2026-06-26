import { describe, expect, it } from "vitest";
import { pendingTurnForView } from "./pendingTurnForView.js";

const turn = (over = {}) => ({
  requestId: "r",
  profile: "muse",
  sessionId: "A",
  launchSessionId: "A",
  at: 1,
  ...over,
});
const map = (...turns) => Object.fromEntries(turns.map((t) => [t.requestId, t]));
const profileView = (sessionId) => ({ kind: "profile", profile: "muse", sessionId });

describe("pendingTurnForView", () => {
  it("returns the turn for the session being viewed", () => {
    const t = turn();
    expect(pendingTurnForView({ pendingTurns: map(t), view: profileView("A"), activeProfileName: "muse" })).toBe(t);
  });

  it("hides a session-A turn while viewing session B (the leak)", () => {
    const t = turn();
    expect(pendingTurnForView({ pendingTurns: map(t), view: profileView("B"), activeProfileName: "muse" })).toBeNull();
  });

  it("picks the right turn when several chats stream at once", () => {
    const a = turn({ requestId: "ra", sessionId: "A", launchSessionId: "A" });
    const b = turn({ requestId: "rb", sessionId: "B", launchSessionId: "B" });
    const turns = map(a, b);
    expect(pendingTurnForView({ pendingTurns: turns, view: profileView("A"), activeProfileName: "muse" })).toBe(a);
    expect(pendingTurnForView({ pendingTurns: turns, view: profileView("B"), activeProfileName: "muse" })).toBe(b);
  });

  it("hides a background session turn when switching to a fresh composer", () => {
    const t = turn();
    expect(pendingTurnForView({ pendingTurns: map(t), view: profileView(null), activeProfileName: "muse" })).toBeNull();
  });

  it("shows a brand-new chat before session_start (no id yet, view still null)", () => {
    const t = turn({ sessionId: null, launchSessionId: null });
    expect(pendingTurnForView({ pendingTurns: map(t), view: profileView(null), activeProfileName: "muse" })).toBe(t);
    expect(pendingTurnForView({ pendingTurns: map(t), view: { kind: "empty" }, activeProfileName: "muse" })).toBe(t);
  });

  it("keeps a brand-new chat visible after session_start while the view lags the real id", () => {
    const t = turn({ sessionId: "new-real-id", launchSessionId: null });
    expect(pendingTurnForView({ pendingTurns: map(t), view: profileView(null), activeProfileName: "muse" })).toBe(t);
  });

  it("keeps a brand-new chat visible once reply navigates the view to the real id", () => {
    const t = turn({ sessionId: "new-real-id", launchSessionId: null });
    expect(pendingTurnForView({ pendingTurns: map(t), view: profileView("new-real-id"), activeProfileName: "muse" })).toBe(t);
  });

  it("defensive: if two new-chat turns ever overlap on a blank composer, prefers the most recent", () => {
    const older = turn({ requestId: "old", sessionId: "x", launchSessionId: null, at: 1 });
    const newer = turn({ requestId: "new", sessionId: "y", launchSessionId: null, at: 2 });
    expect(pendingTurnForView({ pendingTurns: map(older, newer), view: profileView(null), activeProfileName: "muse" })).toBe(newer);
  });

  it("does not leak a background session turn into the new-chat hero", () => {
    const t = turn();
    expect(pendingTurnForView({ pendingTurns: map(t), view: { kind: "empty" }, activeProfileName: "muse" })).toBeNull();
  });

  it("ignores a turn from another profile", () => {
    const t = turn({ profile: "other" });
    expect(pendingTurnForView({ pendingTurns: map(t), view: profileView("A"), activeProfileName: "muse" })).toBeNull();
  });

  it("returns null when no turns are in flight", () => {
    expect(pendingTurnForView({ pendingTurns: {}, view: profileView("A"), activeProfileName: "muse" })).toBeNull();
  });
});
