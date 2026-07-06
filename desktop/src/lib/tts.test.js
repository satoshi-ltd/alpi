import { describe, it, expect, beforeEach, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { enqueueTts, clearTtsQueue, scriptFor, stripMarkdown } from "./tts.js";

beforeEach(() => {
  clearTtsQueue();
  vi.clearAllMocks();
});

describe("stripMarkdown", () => {
  it("drops code fences, headings, and link syntax", () => {
    expect(stripMarkdown("# Hi\n```x```\n[a](u) **b**")).toBe("Hi a b");
  });

  it("removes emojis, arrows and table pipes", () => {
    expect(stripMarkdown("Done ✅🚀 a → b | c ⭐")).toBe("Done a b c");
  });

  it("reduces bare URLs to their domain", () => {
    expect(stripMarkdown("see https://github.com/soyjavi/alf/pull/1 now")).toBe(
      "see github.com now",
    );
  });
});

describe("scriptFor", () => {
  it("returns the daemon script when available", async () => {
    invoke.mockResolvedValue("Spoken version.");
    await expect(scriptFor("doc", "Done ✅")).resolves.toBe("Spoken version.");
    expect(invoke).toHaveBeenCalledWith("voice_script", { profile: "doc", text: "Done ✅" });
  });

  it("falls back to local strip when the daemon call fails", async () => {
    invoke.mockRejectedValue(new Error("offline"));
    await expect(scriptFor("doc", "Done ✅ **ok**")).resolves.toBe("Done ok");
  });

  it("falls back when the daemon returns an empty script", async () => {
    invoke.mockResolvedValue("  ");
    await expect(scriptFor("doc", "Done ✅ ok")).resolves.toBe("Done ok");
  });

  it("skips the daemon entirely without a profile", async () => {
    await expect(scriptFor(null, "Done ✅ ok")).resolves.toBe("Done ok");
    expect(invoke).not.toHaveBeenCalled();
  });
});

describe("enqueueTts", () => {
  it("skips empty / markdown-only text without calling the synth", () => {
    enqueueTts({ key: "k", profile: "p", voice: "v", text: "   " });
    enqueueTts({ key: "k2", profile: "p", voice: "v", text: "```only fence```" });
    expect(invoke).not.toHaveBeenCalled();
  });

  it("asks the daemon for a script, then synthesizes it", async () => {
    invoke.mockImplementation(async (cmd) =>
      cmd === "voice_script" ? "Spoken version." : "",
    );
    enqueueTts({ key: "k", profile: "p", voice: "v", text: "hello there" });
    await vi.waitFor(() =>
      expect(invoke.mock.calls.map(([cmd]) => cmd)).toContain("tts_synthesize"),
    );
    expect(invoke.mock.calls.map(([cmd]) => cmd)[0]).toBe("voice_script");
    const synthCall = invoke.mock.calls.find(([cmd]) => cmd === "tts_synthesize");
    expect(synthCall[1].text).toBe("Spoken version.");
  });

  it("clearTtsQueue drops pending items so a later flush is empty", async () => {
    enqueueTts({ key: "a", profile: "p", voice: "v", text: "one" });
    enqueueTts({ key: "b", profile: "p", voice: "v", text: "two" });
    enqueueTts({ key: "c", profile: "p", voice: "v", text: "three" });
    clearTtsQueue();
    await new Promise((r) => setTimeout(r, 0));
    expect(invoke.mock.calls.filter(([cmd]) => cmd === "tts_synthesize").length)
      .toBeLessThanOrEqual(1);
  });
});
