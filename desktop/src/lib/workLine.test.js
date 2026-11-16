import { describe, expect, it } from "vitest";
import { stepPhrase, stepVerb, workClock, workSummary } from "../../../common/workLine.mjs";

describe("work line words", () => {
  it("names a step by what it does to its target", () => {
    expect(stepPhrase("read_file", "deploy.log")).toBe("Reading deploy.log");
    expect(stepPhrase("terminal", "npm test")).toBe("Running npm test");
    expect(stepPhrase("web_fetch", "status.example.com")).toBe("Fetching status.example.com");
    expect(stepPhrase("grep", "")).toBe("Searching");
    expect(stepVerb("memory")).toBe("Remembering");
  });

  it("falls back to the tool's own name for a tool it does not know", () => {
    expect(stepPhrase("weird_tool", "x")).toBe("Using weird_tool · x");
    expect(stepPhrase("weird_tool")).toBe("Using weird_tool");
  });

  it("reads the clock in whole seconds and minutes", () => {
    expect(workClock(0)).toBe("");
    expect(workClock(0.4)).toBe("0.4s");
    expect(workClock(7.04)).toBe("7s");
    expect(workClock(64)).toBe("1m 4s");
    expect(workClock(120)).toBe("2m");
  });
});

describe("workSummary", () => {
  const tool = (name, ok, seconds = 1, target = "") => ({ kind: "tool", name, ok, seconds, target });

  it("is running while a tool runs and names that tool", () => {
    const s = workSummary([tool("read_file", true), tool("web_fetch", null, 0, "status.example.com")]);
    expect(s).toMatchObject({ running: true, phrase: "Fetching status.example.com" });
  });

  it("says Thinking while a live thought is the newest step", () => {
    expect(workSummary([tool("grep", true), { kind: "thought", live: true }], { thinking: true }).phrase).toBe("Thinking");
  });

  it("counts steps, failures and time once done, ignoring empty sub-second thoughts", () => {
    const s = workSummary([{ kind: "thought", text: "plan", seconds: 3 }, tool("grep", true, 0.4), tool("terminal", false, 2), { kind: "thought", text: "", seconds: 0.3 }]);
    expect(s).toEqual({ running: false, phrase: "", steps: 3, failed: 1, seconds: 5.4 });
  });

  it("stays running while the turn runs even between rounds, and says Thinking", () => {
    expect(workSummary([tool("grep", true)], { running: true })).toMatchObject({ running: true, phrase: "Thinking" });
  });

  it("measures done work as the wall span of the tools plus a leading thought", () => {
    const items = [{ kind: "thought", text: "plan", seconds: 3 }, { ...tool("grep", true, 5), start: 10 }, { ...tool("read_file", true, 5), start: 11 }, { ...tool("terminal", true, 2), start: 30 }];
    expect(workSummary(items).seconds).toBe(25);
  });

  it("adds the thinking after the last tool to the done time", () => {
    const items = [{ ...tool("grep", true, 10), start: 0 }, { kind: "thought", text: "wrap up", seconds: 30 }];
    expect(workSummary(items).seconds).toBe(40);
  });

  it("says Writing while answer text streams between rounds", () => {
    expect(workSummary([tool("grep", true)], { running: true, writing: true }).phrase).toBe("Writing");
  });
});

