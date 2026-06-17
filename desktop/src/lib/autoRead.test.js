import { describe, it, expect } from "vitest";
import { autoReadText, consumeAutoRead } from "./autoRead.js";

describe("autoReadText", () => {
  it("prefers the just-streamed reply over the persisted last turn (which can still hold the previous turn)", () => {
    expect(autoReadText("the new reply", [{ assistant: "the previous reply" }])).toBe("the new reply");
  });

  it("falls back to the last persisted turn when there is no streamed reply", () => {
    expect(autoReadText("", [{ assistant: "persisted" }])).toBe("persisted");
  });

  it("returns empty string when neither source has text", () => {
    expect(autoReadText("", [])).toBe("");
    expect(autoReadText("", null)).toBe("");
    expect(autoReadText(undefined, undefined)).toBe("");
  });
});

describe("consumeAutoRead", () => {
  it("speaks the streamed reply when auto-read is on", () => {
    expect(consumeAutoRead("new reply", true, [{ assistant: "prev" }]))
      .toEqual({ speak: "new reply", nextStreamed: "" });
  });

  it("clears the streamed reply but speaks nothing when auto-read is off — so it can't go stale across turns", () => {
    expect(consumeAutoRead("stale reply", false, [{ assistant: "prev" }]))
      .toEqual({ speak: "", nextStreamed: "" });
  });
});
