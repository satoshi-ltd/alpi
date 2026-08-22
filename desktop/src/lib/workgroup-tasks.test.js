import { describe, it, expect } from "vitest";
import {
  classifyMessage,
  deriveTasks,
  doneOutcome,
  findLatestTask,
  parseDone,
  parseSkip,
  parseTaskOpen,
  parseWorking,
  tasksFromFold,
  validateTaskShape,
} from "./workgroup-tasks.js";

const HUB = "hub-pubkey";
const PEER = "peer-pubkey";

describe("classifyMessage", () => {
  it("routes #task with slug to the task branch", () => {
    const c = classifyMessage("#task #adr Ship ADR\n\nbody");
    expect(c.variant).toBe("task");
    expect(c.task?.slug).toBe("adr");
  });

  it("slug-less #task is prose", () => {
    expect(classifyMessage("#task Ship ADR").variant).toBe("message");
  });

  it("routes #done / #skip / #working", () => {
    expect(classifyMessage("#done shipped").variant).toBe("done");
    expect(classifyMessage("#skip no angle").variant).toBe("skip");
    expect(classifyMessage("#working fetching").variant).toBe("working");
  });

  it("treats a post with both #task and #done as prose (ambiguity rule, mirrors backend)", () => {
    expect(classifyMessage("#task #combined Wrap\n#done shipped already").variant).toBe("message");
  });
});

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

describe("deriveTasks", () => {
  it("a peer #skip never closes the hub task", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #opener-voice Verdict-first or context-first openers?" },
      { seq: 2, from_pubkey: PEER, body: "#skip waiting on FX data" },
    ];
    const [task] = deriveTasks(thread, HUB);
    expect(task.slug).toBe("opener-voice");
    expect(task.status).not.toBe("skip");
    expect(task.status).toBe("working");
  });

  it("a new hub #task preempts the previous one", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #first First" },
      { seq: 2, from_pubkey: PEER, body: "some input" },
      { seq: 3, from_pubkey: HUB, body: "#task #second Second" },
    ];
    const tasks = deriveTasks(thread, HUB);
    expect(tasks).toHaveLength(2);
    expect(tasks[0].status).toBe("preempted");
    expect(tasks[1].status).toBe("working");
  });

  it("only the hub closes with #done", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #cite-cwv Should memos cite Google?" },
      { seq: 2, from_pubkey: PEER, body: "#done not the hub" },
      { seq: 3, from_pubkey: HUB, body: "#done yes, with caveats" },
    ];
    const [task] = deriveTasks(thread, HUB);
    expect(task.status).toBe("done");
  });

  it("a post with both #task and #done is prose, not a task", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #combined Wrap up\n#done shipped already" },
    ];
    expect(deriveTasks(thread, HUB)).toHaveLength(0);
  });

  it("a combined #task+#done post never closes an active task", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #live In progress" },
      { seq: 2, from_pubkey: HUB, body: "#task #other Other\n#done both markers" },
    ];
    const [task] = deriveTasks(thread, HUB);
    expect(deriveTasks(thread, HUB)).toHaveLength(1);
    expect(task.slug).toBe("live");
    expect(task.status).toBe("working");
  });

  it("the still-active last task stays working after a peer skip", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #cite-cwv Cite?" },
      { seq: 2, from_pubkey: HUB, body: "#done shipped" },
      { seq: 3, from_pubkey: HUB, body: "#task #opener-voice Openers?" },
      { seq: 4, from_pubkey: PEER, body: "#skip" },
    ];
    const tasks = deriveTasks(thread, HUB);
    expect(tasks.map((t) => t.status)).toEqual(["done", "working"]);
  });

  it("a #working or #skip line shadows a #done further down the same post", () => {
    const base = [{ seq: 1, from_pubkey: HUB, body: "#task #live In progress" }];
    for (const signal of ["#working", "#skip"]) {
      const tasks = deriveTasks(
        [...base, { seq: 2, from_pubkey: HUB, body: `${signal} still going\n#done shipped` }],
        HUB,
      );
      expect(tasks.map((t) => t.status)).toEqual(["working"]);
      expect(tasks[0].contributions).toBe(1);
    }
  });

  it("a bare #done line carries no result and never closes a task", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #live In progress" },
      { seq: 2, from_pubkey: HUB, body: "#done" },
    ];
    expect(deriveTasks(thread, HUB).map((t) => t.status)).toEqual(["working"]);
  });
});

describe("closeStatus", () => {
  it("keeps a deliberate skip and a BLOCKED close out of done", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #media-config wire the logo" },
      { seq: 2, from_pubkey: HUB, body: "#done skipped · no config change needed" },
      { seq: 3, from_pubkey: HUB, body: "#task #media-build rebuild" },
      { seq: 4, from_pubkey: HUB, body: "#done BLOCKED · the template cannot build" },
      { seq: 5, from_pubkey: HUB, body: "#task #media-qa audit" },
      { seq: 6, from_pubkey: HUB, body: "#done qa green" },
    ];
    expect(deriveTasks(thread, HUB).map((t) => t.status)).toEqual([
      "skipped",
      "blocked",
      "done",
    ]);
  });

  it("marks a preempted task as preempted, not skipped", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #first go" },
      { seq: 2, from_pubkey: HUB, body: "#task #second go" },
    ];
    expect(deriveTasks(thread, HUB)[0].status).toBe("preempted");
  });
});

describe("doneOutcome", () => {
  it("reads the outcome off the #done line, not the synthesis above it", () => {
    expect(doneOutcome("Everything shipped fine\n#done BLOCKED · cannot build")).toBe("blocked");
    expect(doneOutcome("Wrote the copy\n#done skipped · no config change needed")).toBe("skipped");
    expect(doneOutcome("@pixel #done qa green")).toBe("done");
  });
});

describe("tasksFromFold", () => {
  it("orders closed rows by seq, maps outcomes and appends the open task", () => {
    const rows = tasksFromFold({
      active: { slug: "media-qa", title: "audit", opened_seq: 44 },
      closed: [
        { slug: "enrich", result: "skipped · nothing to enrich", closed_seq: 42, blocked: false },
        { slug: "setup", result: "setup green", closed_seq: 41, blocked: false },
      ],
    });
    expect(rows.map((r) => [r.slug, r.status, r.seq])).toEqual([
      ["setup", "done", 41],
      ["enrich", "skipped", 42],
      ["media-qa", "working", 44],
    ]);
  });

  it("trusts the daemon blocked flag over a close text that reads clean", () => {
    const [row] = tasksFromFold({
      active: null,
      closed: [{ slug: "enrich", result: "all good", closed_seq: 9, blocked: true }],
    });
    expect(row.status).toBe("blocked");
  });

  it("a preempted close from the fold is never green", () => {
    const rows = tasksFromFold({
      active: null,
      closed: [
        { slug: "first", result: "preempted by #second", closed_seq: 2, blocked: false },
        { slug: "second", result: "second green", closed_seq: 3, blocked: false },
      ],
    });
    expect(rows.map((r) => r.status)).toEqual(["preempted", "done"]);
  });

  it("is null when the fold is unavailable so the caller falls back to the transcript", () => {
    expect(tasksFromFold(null)).toBeNull();
    expect(tasksFromFold(undefined)).toBeNull();
  });
});
