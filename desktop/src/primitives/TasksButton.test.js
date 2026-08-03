import { describe, it, expect } from "vitest";
import { deriveTasks, doneOutcome, tasksFromFold } from "./TasksButton.jsx";

const HUB = "hub-pubkey";
const PEER = "peer-pubkey";

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
