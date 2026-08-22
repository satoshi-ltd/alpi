import { describe, it, expect } from "vitest";

import { turnParts } from "../../../common/reasoningSteps.mjs";

describe("turnParts", () => {
  it("empty turn", () => {
    expect(turnParts({})).toEqual({ tools: [], askUsers: [], reasoning: "", reasonedSeconds: undefined });
  });

  it("consolidates every tool into one list and reasoning into one block", () => {
    const turn = {
      reasoning: "think A\n\nthink B",
      reasoned_s: 12,
      tools: [
        { name: "read", args: { file_path: "a" }, ok: true, reasoning: "think A" },
        { name: "write", args: { file_path: "b" }, ok: null, reasoning: "think B" },
      ],
    };
    const parts = turnParts(turn);
    expect(parts.tools.map((t) => t.name)).toEqual(["read", "write"]);
    expect(parts.reasoning).toBe("think A\n\nthink B");
    expect(parts.reasonedSeconds).toBe(12);
    expect(parts.askUsers).toEqual([]);
  });

  it("streaming: consolidates per-tool reasoning with the trailing preview", () => {
    const turn = {
      reasoning: "final thought",
      tools: [
        { name: "search", reasoning: "let me look", ok: true },
        { name: "read", reasoning: "now read it", ok: null },
      ],
    };
    expect(turnParts(turn).reasoning).toBe("let me look\n\nnow read it\n\nfinal thought");
  });

  it("persisted: does not double per-tool reasoning already in turn.reasoning", () => {
    const turn = {
      reasoning: "let me look\n\nnow read it\n\nfinal synthesis",
      tools: [
        { name: "search", reasoning: "let me look", ok: true },
        { name: "read", reasoning: "now read it", ok: true },
      ],
    };
    expect(turnParts(turn).reasoning).toBe("let me look\n\nnow read it\n\nfinal synthesis");
  });

  it("keeps ask_user out of the tool list, surfaces answered ones", () => {
    const turn = {
      tools: [
        { name: "read", args: {}, ok: true },
        { name: "ask_user", args: { question: "which?" }, output: "the blue one" },
        { name: "ask_user", args: { question: "empty?" }, output: "  " },
      ],
    };
    const parts = turnParts(turn);
    expect(parts.tools.map((t) => t.name)).toEqual(["read"]);
    expect(parts.askUsers).toEqual([
      { tool_id: undefined, question: "which?", result: "the blue one" },
    ]);
  });
});
