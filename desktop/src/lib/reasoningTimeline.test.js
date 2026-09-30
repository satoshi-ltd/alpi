import { describe, expect, it } from "vitest";

import { lastLine, processTimeline } from "./reasoningTimeline.js";

const shape = (entries) => entries.map((e) => (e.kind === "tool" ? `tool:${e.tool.name}` : `thought:${e.text}:${e.seconds ?? "-"}`));

describe("processTimeline", () => {
  it("interleaves each reasoning span before the tool it led to, then the trailing thought", () => {
    const tools = [
      { tool_id: "a", name: "read_file", reasoning: "read the log" },
      { tool_id: "b", name: "grep" },
      { tool_id: "c", name: "terminal", reasoning: "try the lint" },
    ];
    expect(shape(processTimeline(tools, "read the log\n\ntry the lint\n\nwrap up"))).toEqual([
      "thought:read the log:-",
      "tool:read_file",
      "tool:grep",
      "thought:try the lint:-",
      "tool:terminal",
      "thought:wrap up:-",
    ]);
  });

  it("puts reasoning that only happened after the tools last", () => {
    const tools = [{ tool_id: "a", name: "grep" }, { tool_id: "b", name: "read_file" }];
    expect(shape(processTimeline(tools, "now answer", 5))).toEqual(["tool:grep", "tool:read_file", "thought:now answer:5"]);
  });

  it("drops ask_user steps but keeps the reasoning that led to them", () => {
    const entries = processTimeline([{ tool_id: "a", name: "ask_user", reasoning: "need a date" }], "need a date");
    expect(shape(entries)).toEqual(["thought:need a date:-"]);
  });

  it("gives a lone span the turn total and the tail whatever the live spans did not account for", () => {
    expect(processTimeline([{ tool_id: "a", name: "grep", reasoning: "look" }], "look", 4)[0].seconds).toBe(4);
    const live = processTimeline(
      [{ tool_id: "a", name: "grep", reasoning: "look", reasoned_s: 3 }],
      "summarize",
      7,
    );
    expect(shape(live)).toEqual(["thought:look:3", "tool:grep", "thought:summarize:4"]);
  });

  it("keeps an old multi-span turn as one Thought row with the total, first", () => {
    const entries = processTimeline(
      [{ tool_id: "a", name: "grep", reasoning: "look" }],
      "look\n\nsummarize",
      9,
      undefined,
      { mergeUnattributed: true },
    );
    expect(shape(entries)).toEqual(["thought:look\n\nsummarize:9", "tool:grep"]);
    expect(entries[0].timeline).toEqual([
      { kind: "text", text: "look" },
      { kind: "tools", names: ["grep"] },
      { kind: "text", text: "summarize" },
    ]);
  });

  it("interleaves unattributed spans while live, without the merge", () => {
    const entries = processTimeline([{ tool_id: "a", name: "grep", reasoning: "look" }], "look\n\nsummarize", 9);
    expect(shape(entries)).toEqual(["thought:look:-", "tool:grep", "thought:summarize:-"]);
  });

  it("puts each stored span's own text before the prose on the tools, on a daemon-shaped turn", () => {
    const turn = {
      reasoning: "Plan the search.\n\nOkay, one match.\n\nWrite it up.",
      reasoned_s: 7.5,
      reasoning_spans: [
        { seconds: 2.1, before_tool: 0, text: "Plan the search." },
        { seconds: 1.4, before_tool: 1, text: "Okay, one match." },
        { seconds: 4.0, before_tool: 2, text: "Write it up." },
      ],
      tools: [
        { name: "grep", ok: true, reasoning: "Let me look." },
        { name: "read_file", ok: true },
      ],
    };
    const entries = processTimeline(turn.tools, turn.reasoning, turn.reasoned_s, turn.reasoning_spans, { mergeUnattributed: true });
    expect(shape(entries)).toEqual([
      "thought:Plan the search.\n\nLet me look.:2.1",
      "tool:grep",
      "thought:Okay, one match.:1.4",
      "tool:read_file",
      "thought:Write it up.:4",
    ]);
  });

  it("places stored spans with their own seconds: 3 spans around 2 tools", () => {
    const tools = [
      { tool_id: "a", name: "grep", reasoning: "look" },
      { tool_id: "b", name: "read_file", reasoning: "open it" },
    ];
    const spans = [{ seconds: 2, before_tool: 0 }, { seconds: 1.5, before_tool: 1 }, { seconds: 4, before_tool: 2 }];
    expect(shape(processTimeline(tools, "look\n\nopen it\n\nanswer now", 9, spans))).toEqual([
      "thought:look:2",
      "tool:grep",
      "thought:open it:1.5",
      "tool:read_file",
      "thought:answer now:4",
    ]);
  });

  it("gives a stored span before the answer its own seconds, not the turn total", () => {
    const entries = processTimeline([{ tool_id: "a", name: "grep" }], "summarize", 12, [{ seconds: 3, before_tool: 1 }]);
    expect(shape(entries)).toEqual(["tool:grep", "thought:summarize:3"]);
  });

  it("falls back to the lone-span total when reasoning_spans is absent", () => {
    expect(shape(processTimeline([{ tool_id: "a", name: "grep" }], "summarize", 12))).toEqual(["tool:grep", "thought:summarize:12"]);
    expect(shape(processTimeline([{ tool_id: "a", name: "grep" }], "summarize", 12, []))).toEqual(["tool:grep", "thought:summarize:12"]);
  });

  it("keeps the stored prose after each span's own text on a daemon-shaped turn", () => {
    const turn = {
      reasoning: "Plan the search.\n\nOkay, one match.\n\nWrite it up.",
      reasoned_s: 7.5,
      reasoning_spans: [
        { seconds: 2.1, before_tool: 0, text: "Plan the search." },
        { seconds: 1.4, before_tool: 1, text: "Okay, one match." },
        { seconds: 1.8, before_tool: 2 },
      ],
      tools: [
        { name: "grep", ok: true, reasoning: "Plan the search." },
        { name: "read_file", ok: true, reasoning: "Let me open that file." },
      ],
    };
    const entries = processTimeline(turn.tools, turn.reasoning, turn.reasoned_s, turn.reasoning_spans, { mergeUnattributed: true });
    expect(shape(entries)).toEqual([
      "thought:Plan the search.:2.1",
      "tool:grep",
      "thought:Okay, one match.\n\nLet me open that file.:1.4",
      "tool:read_file",
      "thought::1.8",
    ]);
  });

  it("shows prose before a tool even when no span led to it", () => {
    const entries = processTimeline(
      [{ name: "grep", ok: true }, { name: "read_file", ok: true, reasoning: "Now the file." }],
      "x",
      3,
      [{ seconds: 3, before_tool: 0, text: "x" }],
    );
    expect(shape(entries)).toEqual(["thought:x:3", "tool:grep", "thought:Now the file.:-", "tool:read_file"]);
  });

  it("keys entries stably and uniquely", () => {
    const keys = processTimeline([{ tool_id: "x", name: "grep", reasoning: "r" }], "r\n\ntail").map((e) => e.key);
    expect(keys).toEqual(["r0", "t:x", "r1"]);
  });

  it("keeps a live span's key when tool_start moves it before the tool", () => {
    const streaming = processTimeline([], "plan it");
    const moved = processTimeline([{ tool_id: "a", name: "grep", ok: null, reasoning: "plan it" }], "");
    expect(streaming[0].key).toBe(moved[0].key);
  });

  it("drops a stored sub-second span with no text", () => {
    const entries = processTimeline(
      [{ tool_id: "a", name: "grep" }, { tool_id: "b", name: "read_file" }],
      "",
      2,
      [{ seconds: 0.4, before_tool: 1 }],
    );
    expect(shape(entries)).toEqual(["tool:grep", "tool:read_file"]);
  });
});

describe("lastLine", () => {
  it("returns the last non-empty line", () => {
    expect(lastLine("a\nb\n\n")).toBe("b");
    expect(lastLine("")).toBe("");
  });
});
