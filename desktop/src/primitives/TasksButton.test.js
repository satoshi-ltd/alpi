import { describe, it, expect } from "vitest";
import { deriveTasks } from "./TasksButton.jsx";

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

  it("a new hub #task preempts the previous one as skip", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #first First" },
      { seq: 2, from_pubkey: PEER, body: "some input" },
      { seq: 3, from_pubkey: HUB, body: "#task #second Second" },
    ];
    const tasks = deriveTasks(thread, HUB);
    expect(tasks).toHaveLength(2);
    expect(tasks[0].status).toBe("skip");
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
