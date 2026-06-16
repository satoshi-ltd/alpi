import { describe, it, expect } from "vitest";

import { reasoningSteps } from "./reasoningSteps.js";

describe("reasoningSteps", () => {
  it("returns nothing for an empty turn", () => {
    expect(reasoningSteps({})).toEqual([]);
    expect(reasoningSteps({ tools: [] })).toEqual([]);
  });

  it("active: injects an empty live thinking step when nothing is streaming yet", () => {
    expect(reasoningSteps({}, { active: true })).toEqual([{ kind: "reasoning", text: "", trailing: true }]);
  });

  it("active: no live thinking step while a tool is running", () => {
    const steps = reasoningSteps({ tools: [{ name: "search", ok: null }] }, { active: true });
    expect(steps.some((s) => s.kind === "reasoning")).toBe(false);
  });

  it("active: does not duplicate when real trailing reasoning is present", () => {
    const steps = reasoningSteps({ reasoning: "thinking now" }, { active: true });
    expect(steps.filter((s) => s.kind === "reasoning")).toHaveLength(1);
    expect(steps[0].text).toBe("thinking now");
  });

  it("no tools: one trailing reasoning segment carrying reasoned_s", () => {
    const steps = reasoningSteps({ reasoning: "just thinking", reasoned_s: 4 });
    expect(steps).toEqual([{ kind: "reasoning", text: "just thinking", seconds: 4, trailing: true }]);
  });

  it("interleaves reasoning before each batch in execution order", () => {
    const turn = {
      at: 0,
      reasoned_s: 3,
      tools: [
        { name: "search", reasoning: "find data", at: 3, duration_s: 1 },
        { name: "read_file", reasoning: "now read it", at: 6, duration_s: 2 },
      ],
    };
    const steps = reasoningSteps(turn);
    expect(steps.map((s) => s.kind)).toEqual(["reasoning", "tools", "reasoning", "tools"]);
    expect(steps[0]).toMatchObject({ text: "find data", seconds: 3 });
    expect(steps[2]).toMatchObject({ text: "now read it", seconds: 2 });
  });

  it("groups consecutive tools of one batch under a single tools step", () => {
    const turn = {
      tools: [
        { name: "a", reasoning: "go", at: 1 },
        { name: "b", at: 2 },
        { name: "c", at: 3 },
      ],
    };
    const steps = reasoningSteps(turn);
    expect(steps.map((s) => s.kind)).toEqual(["reasoning", "tools"]);
    expect(steps[1].tools.map((t) => t.name)).toEqual(["a", "b", "c"]);
  });

  it("does not double-render when turn.reasoning is the join of per-tool parts", () => {
    const turn = {
      reasoning: "first.\n\nsecond.",
      tools: [
        { name: "a", reasoning: "first.", at: 1 },
        { name: "b", reasoning: "second.", at: 2 },
      ],
    };
    const steps = reasoningSteps(turn);
    expect(steps.filter((s) => s.kind === "reasoning").map((s) => s.text)).toEqual(["first.", "second."]);
    expect(steps.some((s) => s.trailing)).toBe(false);
  });

  it("keeps genuinely-trailing reasoning that extends past the shown parts", () => {
    const turn = {
      reasoning: "first.\n\nfinal synthesis.",
      tools: [{ name: "a", reasoning: "first.", at: 1 }],
    };
    const trailing = reasoningSteps(turn).find((s) => s.trailing);
    expect(trailing.text).toBe("final synthesis.");
  });

  it("renders ask_user as its own segment in order", () => {
    const turn = {
      tools: [
        { name: "search", reasoning: "look", at: 1 },
        { name: "ask_user", args: { question: "which?" }, output: "this one", at: 2 },
      ],
    };
    const steps = reasoningSteps(turn);
    expect(steps.map((s) => s.kind)).toEqual(["reasoning", "tools", "askUser"]);
    expect(steps[2]).toMatchObject({ question: "which?", result: "this one" });
  });

  it("renders the reasoning that precedes an ask_user (not dropped)", () => {
    const turn = {
      tools: [
        { name: "ask_user", reasoning: "I need to clarify this", args: { question: "which?" }, output: "A", at: 1 },
      ],
    };
    const steps = reasoningSteps(turn);
    expect(steps.map((s) => s.kind)).toEqual(["reasoning", "askUser"]);
    expect(steps[0].text).toBe("I need to clarify this");
    expect(steps[1].result).toBe("A");
  });

  it("falls back to reasoned_s for the first segment when timestamps are absent", () => {
    const turn = { reasoned_s: 7, tools: [{ name: "a", reasoning: "go" }] };
    expect(reasoningSteps(turn)[0]).toMatchObject({ text: "go", seconds: 7 });
  });
});
