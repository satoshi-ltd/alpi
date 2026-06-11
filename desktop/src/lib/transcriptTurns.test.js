import { describe, it, expect } from "vitest";
import { dropInflightStub } from "./transcriptTurns.js";

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
