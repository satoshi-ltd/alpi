import { describe, expect, it } from "vitest";

import { lastLine, reasoningTimeline } from "./reasoningTimeline.js";

describe("reasoningTimeline", () => {
  it("interleaves each segment before the tools it led to, then the trailing thought", () => {
    const tools = [
      { name: "read_file", reasoning: "read the log" },
      { name: "grep" },
      { name: "terminal", reasoning: "try the lint" },
    ];
    const items = reasoningTimeline(tools, "read the log\n\ntry the lint\n\nwrap up");
    expect(items).toEqual([
      { kind: "text", text: "read the log" },
      { kind: "tools", names: ["read_file", "grep"] },
      { kind: "text", text: "try the lint" },
      { kind: "tools", names: ["terminal"] },
      { kind: "text", text: "wrap up" },
    ]);
  });

  it("drops trailing tool markers and ignores ask_user", () => {
    const items = reasoningTimeline([{ name: "grep", reasoning: "look" }, { name: "ask_user" }], "look");
    expect(items).toEqual([{ kind: "text", text: "look" }]);
  });
});

describe("lastLine", () => {
  it("returns the last non-empty line", () => {
    expect(lastLine("a\nb\n\n")).toBe("b");
    expect(lastLine("")).toBe("");
  });
});
