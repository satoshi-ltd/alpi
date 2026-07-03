import { describe, it, expect } from "vitest";
import { dropInflightStub, isLastTurnInFlight } from "./transcriptTurns.js";

const pending = { user: "hola", profile: "doc", sessionId: "s1" };

describe("dropInflightStub", () => {
  it("drops a trailing user-only stub that matches the pending message", () => {
    const turns = [
      { user: "first", assistant: "done" },
      { user: "hola", assistant: "", tools: [] },
    ];
    expect(dropInflightStub(turns, pending)).toEqual([{ user: "first", assistant: "done" }]);
  });

  it("keeps a completed turn even when its text repeats the pending message", () => {
    const turns = [{ user: "hola", assistant: "the full reply" }];
    expect(dropInflightStub(turns, pending)).toEqual(turns);
  });

  it("keeps a turn that already has tool activity", () => {
    const turns = [{ user: "hola", assistant: "", tools: [{ tool_id: "t1" }] }];
    expect(dropInflightStub(turns, pending)).toEqual(turns);
  });

  it("does not drop when the last turn is a different message", () => {
    const turns = [{ user: "otra cosa", assistant: "" }];
    expect(dropInflightStub(turns, pending)).toEqual(turns);
  });

  it("is a no-op without a pendingTurn or with no turns", () => {
    const turns = [{ user: "hola", assistant: "" }];
    expect(dropInflightStub(turns, null)).toBe(turns);
    expect(dropInflightStub([], pending)).toEqual([]);
  });
});

describe("isLastTurnInFlight", () => {
  it("is true for a trailing stub when the session is in_flight", () => {
    const turns = [{ user: "hola", assistant: "", tools: [] }];
    expect(isLastTurnInFlight(turns, true)).toBe(true);
  });

  it("is false when the session is not in_flight", () => {
    const turns = [{ user: "hola", assistant: "", tools: [] }];
    expect(isLastTurnInFlight(turns, false)).toBe(false);
  });

  it("is false when the last turn already has a real reply", () => {
    const turns = [{ user: "hola", assistant: "the full reply" }];
    expect(isLastTurnInFlight(turns, true)).toBe(false);
  });

  it("is false when the last turn already has tool activity", () => {
    const turns = [{ user: "hola", assistant: "", tools: [{ tool_id: "t1" }] }];
    expect(isLastTurnInFlight(turns, true)).toBe(false);
  });

  it("is false with no turns", () => {
    expect(isLastTurnInFlight([], true)).toBe(false);
  });
});
