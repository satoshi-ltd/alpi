import { describe, expect, it } from "vitest";
import { rewriteCut } from "./rewriteCut.js";

const ctx = { profileName: "muse", sessionId: "s1" };

describe("rewriteCut", () => {
  it("hides from the pending rewrite turn (survives a cleared draft)", () => {
    const pendingTurn = { profile: "muse", sessionId: "s1", rewriteFromTurn: 2 };
    expect(rewriteCut({ ...ctx, pendingTurn, rewriteDraft: null })).toBe(2);
  });

  it("falls back to the edit-mode draft when no pending rewrite", () => {
    const rewriteDraft = { profile: "muse", sessionId: "s1", turnIndex: 3 };
    expect(rewriteCut({ ...ctx, pendingTurn: null, rewriteDraft })).toBe(3);
  });

  it("pending rewrite wins over the draft", () => {
    const pendingTurn = { profile: "muse", sessionId: "s1", rewriteFromTurn: 1 };
    const rewriteDraft = { profile: "muse", sessionId: "s1", turnIndex: 4 };
    expect(rewriteCut({ ...ctx, pendingTurn, rewriteDraft })).toBe(1);
  });

  it("ignores a pending turn / draft from another profile or session, or a plain send", () => {
    expect(rewriteCut({ ...ctx, pendingTurn: { profile: "x", sessionId: "s1", rewriteFromTurn: 2 }, rewriteDraft: null })).toBeNull();
    expect(rewriteCut({ ...ctx, pendingTurn: { profile: "muse", sessionId: "s2", rewriteFromTurn: 2 }, rewriteDraft: null })).toBeNull();
    expect(rewriteCut({ ...ctx, pendingTurn: { profile: "muse", sessionId: "s1" }, rewriteDraft: null })).toBeNull();
  });
});
