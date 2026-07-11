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

describe("playTts races", () => {
  it("a re-triggered key never lets the aborted chain synthesize (zombie guard)", async () => {
    const { playTts, stopTts } = await import("./tts.js");
    const scripts = [];
    invoke.mockImplementation((cmd) => {
      if (cmd === "voice_script") return new Promise((res) => scripts.push(res));
      return Promise.resolve("");
    });
    const p1 = playTts({ key: "k", profile: "p", voice: "v", text: "hello one" });
    stopTts();
    const p2 = playTts({ key: "k", profile: "p", voice: "v", text: "hello one" });
    await vi.waitFor(() => expect(scripts.length).toBe(2));
    scripts[0]("Spoken by the aborted chain");
    scripts[1]("Spoken by the live chain");
    await Promise.all([p1, p2]);
    const synthCalls = invoke.mock.calls.filter(([c]) => c === "tts_synthesize");
    expect(synthCalls).toHaveLength(1);
    expect(synthCalls[0][1].text).toBe("Spoken by the live chain");
  });

  it("a zombie synth failure cannot clear the live chain's state", async () => {
    const { playTts, stopTts, currentlyPlayingKey } = await import("./tts.js");
    const scripts = [];
    const synths = [];
    invoke.mockImplementation((cmd) => {
      if (cmd === "voice_script") return new Promise((res) => scripts.push(res));
      if (cmd === "tts_synthesize") return new Promise((_res, rej) => synths.push(rej));
      return Promise.resolve("");
    });
    const p1 = playTts({ key: "k", profile: "p", voice: "en-US-AriaNeural", text: "hello one" });
    await vi.waitFor(() => expect(scripts.length).toBe(1));
    scripts[0]("Spoken A");
    await vi.waitFor(() => expect(synths.length).toBe(1));
    stopTts();
    const p2 = playTts({ key: "k", profile: "p", voice: "en-US-AriaNeural", text: "hello one" });
    await vi.waitFor(() => expect(scripts.length).toBe(2));
    synths[0](new Error("zombie boom"));
    await p1;
    // the live chain still owns the key — the zombie error must not null it
    expect(currentlyPlayingKey()).toBe("k");
    scripts[1]("Spoken B");
    await vi.waitFor(() => expect(synths.length).toBe(2));
    synths[1](new Error("live boom"));
    await p2;
  });

  it("queue skips an item whose key is already loading instead of hanging", async () => {
    const { playTts } = await import("./tts.js");
    let releaseManual;
    invoke.mockImplementation((cmd, args) => {
      if (cmd === "voice_script") {
        if (args?.text === "manual") return new Promise((res) => { releaseManual = res; });
        return Promise.resolve("spoken");
      }
      return Promise.resolve("");
    });
    playTts({ key: "k1", profile: "p", voice: "v", text: "manual" });
    enqueueTts({ key: "k1", profile: "p", voice: "v", text: "same key from queue" });
    enqueueTts({ key: "k2", profile: "p", voice: "v", text: "next item" });
    // Without the skipped notification the k1 item hangs the drain and k2 never starts.
    await vi.waitFor(() => {
      const briefs = invoke.mock.calls
        .filter(([c]) => c === "voice_script")
        .map(([, a]) => a.text);
      expect(briefs).toContain("next item");
    });
    releaseManual?.("late");
  });
});
