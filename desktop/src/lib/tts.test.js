import { describe, it, expect, beforeEach, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { enqueueTts, clearTtsQueue, stripMarkdown } from "./tts.js";

beforeEach(() => {
  clearTtsQueue();
  vi.clearAllMocks();
});

describe("stripMarkdown", () => {
  it("drops code fences, headings, and link syntax", () => {
    expect(stripMarkdown("# Hi\n```x```\n[a](u) **b**")).toBe("Hi a b");
  });
});

describe("enqueueTts", () => {
  it("skips empty / markdown-only text without calling the synth", () => {
    enqueueTts({ key: "k", profile: "p", voice: "v", text: "   " });
    enqueueTts({ key: "k2", profile: "p", voice: "v", text: "```only fence```" });
    expect(invoke).not.toHaveBeenCalled();
  });

  it("synthesizes real text via tts_synthesize", async () => {
    enqueueTts({ key: "k", profile: "p", voice: "v", text: "hello there" });
    await vi.waitFor(() => expect(invoke).toHaveBeenCalled());
    expect(invoke.mock.calls[0][0]).toBe("tts_synthesize");
  });

  it("clearTtsQueue drops pending items so a later flush is empty", async () => {
    enqueueTts({ key: "a", profile: "p", voice: "v", text: "one" });
    enqueueTts({ key: "b", profile: "p", voice: "v", text: "two" });
    enqueueTts({ key: "c", profile: "p", voice: "v", text: "three" });
    clearTtsQueue();
    await new Promise((r) => setTimeout(r, 0));
    expect(invoke.mock.calls.length).toBeLessThanOrEqual(1);
  });
});
