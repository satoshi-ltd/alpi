import { describe, expect, it } from "vitest";
import { isChatSessionData } from "./App.jsx";

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
