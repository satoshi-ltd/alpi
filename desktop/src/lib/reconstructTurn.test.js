import { describe, it, expect } from "vitest";
import { reconstructFromEvents } from "./reconstructTurn.js";

const ev = (event, extra = {}, seq = 0, ts = 0) => ({ seq, ts, frame: { event, ...extra } });

describe("reconstructFromEvents", () => {
  it("builds tools with ok/duration and keeps the final answer", () => {
    const r = reconstructFromEvents([
      ev("session_start", { session_id: "s1" }, 1),
      ev("tool_start", { tool_id: "t1", name: "search" }, 2, 100),
      ev("tool_end", { tool_id: "t1", ok: true, output: "hits" }, 3, 104),
      ev("assistant_delta", { text: "the answer" }, 4),
    ]);
    expect(r.tools).toHaveLength(1);
    expect(r.tools[0].name).toBe("search");
    expect(r.tools[0].ok).toBe(true);
    expect(r.tools[0].duration_s).toBe(4);
    expect(r.assistant).toBe("the answer");
    expect(r.sawDone).toBe(false);
    expect(r.finalSessionId).toBe("s1");
  });

  it("attaches inter-tool prose as the tool's reasoning, not the answer", () => {
    const r = reconstructFromEvents([
      ev("assistant_delta", { text: "let me look" }, 1),
      ev("tool_start", { tool_id: "t1", name: "grep" }, 2),
    ]);
    expect(r.tools[0].reasoning).toBe("let me look");
    expect(r.assistant).toBe("");
  });

  it("flags done and carries the session id", () => {
    const r = reconstructFromEvents([ev("done", { session_id: "s9" }, 1)]);
    expect(r.sawDone).toBe(true);
    expect(r.finalSessionId).toBe("s9");
  });

  it("captures an error frame", () => {
    const r = reconstructFromEvents([ev("error", { text: "boom" }, 1)]);
    expect(r.error).toBe("boom");
  });
});
