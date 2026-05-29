import { describe, it, expect } from "vitest";
import {
  findLatestTask,
  parseDone,
  parseSkip,
  parseTaskOpen,
  parseWorking,
  validateTaskShape,
} from "./workgroup-tasks.js";

describe("parseTaskOpen", () => {
  it("returns null on bodies without a #task marker", () => {
    expect(parseTaskOpen("plain message")).toBeNull();
    expect(parseTaskOpen("")).toBeNull();
    expect(parseTaskOpen(null)).toBeNull();
  });

  it("slug-less #task is no longer a task", () => {
    expect(parseTaskOpen("#task Ship ADR")).toBeNull();
    expect(parseTaskOpen("@forge #task Audit pipeline\n\nBody here.")).toBeNull();
  });

  it("extracts an explicit #slug and bolds it in content", () => {
    const post = "#task #onboarding-friction-top3 Top three onboarding friction points\n\nBody here.";
    expect(parseTaskOpen(post)).toEqual({
      slug: "onboarding-friction-top3",
      title: "Top three onboarding friction points",
      content: "**#onboarding-friction-top3** Top three onboarding friction points\n\nBody here.",
    });
  });

  it("accepts a slug without dashes", () => {
    expect(parseTaskOpen("#task #simple Title here")).toEqual({
      slug: "simple",
      title: "Title here",
      content: "**#simple** Title here",
    });
  });

  it("slug normalised to lowercase", () => {
    expect(parseTaskOpen("#task #Mixed-Case Title")).toEqual({
      slug: "mixed-case",
      title: "Title",
      content: "**#mixed-case** Title",
    });
  });

  it("slug-only post (no title text) renders just the bold slug", () => {
    expect(parseTaskOpen("#task #icp-v2")).toEqual({
      slug: "icp-v2",
      title: "",
      content: "**#icp-v2**",
    });
  });
});

describe("validateTaskShape", () => {
  it("passes through bodies without a #task marker", () => {
    expect(validateTaskShape("plain text")).toEqual({ ok: true });
    expect(validateTaskShape("")).toEqual({ ok: true });
    expect(validateTaskShape(null)).toEqual({ ok: true });
  });

  it("accepts well-formed #task #slug posts", () => {
    expect(validateTaskShape("#task #onboarding-friction-top3 …")).toEqual({ ok: true });
    expect(validateTaskShape("#task #icp-v2")).toEqual({ ok: true });
    expect(validateTaskShape("@hub #task #x title")).toEqual({ ok: true });
  });

  it("rejects #task without a slug", () => {
    const v = validateTaskShape("#task no slug here");
    expect(v.ok).toBe(false);
    expect(v.error).toMatch(/#<slug>/);
  });

  it("rejects #task # with malformed slug", () => {
    expect(validateTaskShape("#task #-leading-hyphen Title").ok).toBe(false);
    expect(validateTaskShape("#task # bare hash").ok).toBe(false);
  });
});

describe("parseDone / parseWorking / parseSkip", () => {
  it("returns null when the marker is absent", () => {
    expect(parseDone("plain text")).toBeNull();
    expect(parseWorking("plain text")).toBeNull();
    expect(parseSkip("plain text")).toBeNull();
  });

  it("keeps the full multi-line content after the marker", () => {
    const post = "#done Quórum completo. Síntesis y decisión:\n\n**1.** ORG.2 sube a #1.\n**2.** MEM.3 se mantiene.";
    expect(parseDone(post)).toEqual({
      content: "Quórum completo. Síntesis y decisión:\n\n**1.** ORG.2 sube a #1.\n**2.** MEM.3 se mantiene.",
    });
  });

  it("strips @mentions before the marker", () => {
    expect(parseWorking("@hub #working fetching benchmarks")).toEqual({
      content: "fetching benchmarks",
    });
  });

  it("accepts marker with no trailing summary", () => {
    expect(parseSkip("#skip")).toEqual({ content: "" });
  });

  it("detects #done at the end of a multi-line synthesis (regression: hub closes with synthesis above)", () => {
    const post = "Synthesis before closing.\n\n**Bet 1** — SplitPass.\n\n#done H2 bets framed as three hypotheses.";
    expect(parseDone(post)).toEqual({
      content: "Synthesis before closing.\n\n**Bet 1** — SplitPass.\n\nH2 bets framed as three hypotheses.",
    });
  });

  it("strips the #done keyword on its line but keeps the rest of the body intact", () => {
    expect(parseDone("Top text.\n#done result.\nbottom text.")).toEqual({
      content: "Top text.\nresult.\nbottom text.",
    });
  });
});

describe("findLatestTask", () => {
  it("returns null on empty input", () => {
    expect(findLatestTask([])).toBeNull();
    expect(findLatestTask(null)).toBeNull();
  });

  it("returns the latest #task and folds in a later #done", () => {
    const msgs = [
      { seq: 1, body: "#task #first First", from_pubkey: "HUB" },
      { seq: 2, body: "noise", from_pubkey: "M" },
      { seq: 3, body: "#done shipped", from_pubkey: "HUB" },
    ];
    expect(findLatestTask(msgs, "HUB")).toEqual({
      state: "done",
      slug: "first",
      text: "First",
      seq: 1,
      result: "shipped",
    });
  });

  it("ignores a post carrying both #task and #done (ambiguity rule)", () => {
    const msgs = [
      { seq: 1, body: "#task #combined Wrap\n#done shipped already", from_pubkey: "HUB" },
    ];
    expect(findLatestTask(msgs, "HUB")).toBeNull();
  });

  it("a combined #task+#done post never closes an open task", () => {
    const msgs = [
      { seq: 1, body: "#task #live In progress", from_pubkey: "HUB" },
      { seq: 2, body: "#task #other Other\n#done both markers", from_pubkey: "HUB" },
    ];
    expect(findLatestTask(msgs, "HUB")).toEqual({
      state: "open",
      slug: "live",
      text: "In progress",
      seq: 1,
      result: null,
    });
  });
});
