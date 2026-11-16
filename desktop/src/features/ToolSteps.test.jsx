import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import { readFileSync } from "node:fs";
import { join } from "node:path";

vi.mock("../lib/clipboard.js", () => ({ copyText: vi.fn(async () => true) }));

import { copyText } from "../lib/clipboard.js";
import { ProcessBlock, ToolStep } from "./ToolSteps.jsx";
import { processTimeline } from "../lib/reasoningTimeline.js";
import { workLineKeys } from "../pages/ChatPane.jsx";

function ToolModule({ tools, reasoning, seconds, ...rest }) {
  return <ProcessBlock entries={processTimeline(tools, reasoning, seconds)} {...rest} />;
}

afterEach(() => {
  vi.useRealTimers();
});

describe("ToolStep", () => {
  it("flips the copy button to Copied in place for 1.5 s and raises no toast", async () => {
    vi.useFakeTimers();
    const notify = vi.fn();
    window.notify = notify;
    render(<ToolStep open tool={{ name: "read_file", args: { path: "/a" }, ok: true, duration_s: 0.2, result: "done" }} />);
    await act(async () => {
      fireEvent.click(screen.getByLabelText("Copy result"));
    });
    expect(copyText).toHaveBeenCalledWith("done");
    expect(screen.getByLabelText("Copied")).toBeTruthy();
    expect(screen.queryByLabelText("Copy result")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(1600);
    });
    expect(screen.getByLabelText("Copy result")).toBeTruthy();
    expect(notify).not.toHaveBeenCalled();
    delete window.notify;
  });

  it("opens to the full arguments and the stored result, labelled as an excerpt when capped", () => {
    const result = `${"x".repeat(399)}…`;
    render(<ToolStep tool={{ name: "read_file", args: { path: "/var/log/deploy.log", limit: 200 }, ok: true, duration_s: 0.24, result }} />);
    const head = screen.getByRole("button", { name: /read_file/ });
    expect(head).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("/var/log/deploy.log")).toBeTruthy();
    expect(screen.getByText("0.2s")).toBeTruthy();
    fireEvent.click(head);
    expect(head).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Arguments")).toBeTruthy();
    expect(screen.getByText(/"limit": 200/)).toBeTruthy();
    expect(screen.getByText("· excerpt")).toBeTruthy();
    expect(screen.getByLabelText("Copy arguments")).toBeTruthy();
    expect(screen.getByLabelText("Copy result")).toBeTruthy();
  });

  it("starts a failed call closed and shows its output once opened", () => {
    render(<ToolStep tool={{ name: "terminal", args: { command: "npm run lint" }, ok: false, duration_s: 4.1, output: "1 error" }} />);
    expect(screen.getByRole("button", { name: /terminal/ })).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(screen.getByRole("button", { name: /terminal/ }));
    expect(screen.getByText("failed · 4.1s")).toBeTruthy();
    expect(screen.getByText("1 error")).toBeTruthy();
    expect(screen.getByText("Output")).toBeTruthy();
  });

  it("stays closed when a live call fails", () => {
    const { rerender } = render(<ToolStep tool={{ name: "terminal", args: {}, ok: null }} />);
    expect(screen.getByRole("button", { name: /terminal/ })).toHaveAttribute("aria-expanded", "false");
    rerender(<ToolStep tool={{ name: "terminal", args: {}, ok: false, output: "boom" }} />);
    expect(screen.getByRole("button", { name: /terminal/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("ticks the live duration from the daemon's started_at", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(10_000));
    render(<ToolStep tool={{ name: "web_fetch", args: { url: "https://x.test" }, ok: null, started_at: 7 }} />);
    expect(screen.getByText("3.0s …")).toBeTruthy();
    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByText("4.0s …")).toBeTruthy();
  });

  it("gives memory its own glyph, not the generic chip", () => {
    const { container } = render(<ToolStep tool={{ name: "memory", args: { action: "add" }, ok: true }} />);
    const memorySvg = container.querySelector("svg").innerHTML;
    const chip = render(<ToolStep tool={{ name: "todo", args: {}, ok: true }} />).container.querySelector("svg").innerHTML;
    expect(memorySvg).not.toBe(chip);
  });
});

describe("ProcessBlock", () => {
  const line = () => screen.getByRole("button", { name: /^(Working|Worked)/ });

  it("is one closed line once the work is done: how long, how many steps, how many failed", () => {
    const tools = [
      { tool_id: "a", name: "read_file", args: { path: "a" }, ok: true, duration_s: 0.4 },
      { tool_id: "b", name: "terminal", args: { command: "lint" }, ok: false, output: "1 error", duration_s: 2 },
    ];
    render(<ToolModule tools={tools} reasoning="check it" seconds={3} />);
    expect(line()).toHaveAttribute("aria-expanded", "false");
    expect(line()).toHaveAccessibleName("Worked for 5s · 3 steps · 1 failed");
    expect(screen.queryByText("read_file")).toBeNull();
    expect(screen.queryByText("1 error")).toBeNull();
  });

  it("opens into every step in the order it happened, each step still closed", () => {
    const tools = [
      { tool_id: "a", name: "read_file", args: {}, ok: true, reasoning: "check the log", reasoned_s: 2 },
      { tool_id: "b", name: "grep", args: {}, ok: true },
    ];
    const { container } = render(<ToolModule tools={tools} reasoning={"check the log\n\nsummarize"} seconds={6} />);
    fireEvent.click(line());
    expect(line()).toHaveAttribute("aria-expanded", "true");
    const text = container.textContent;
    expect(text.indexOf("Thought for 2s")).toBeLessThan(text.indexOf("read_file"));
    expect(text.indexOf("read_file")).toBeLessThan(text.indexOf("grep"));
    expect(text.indexOf("grep")).toBeLessThan(text.indexOf("Thought for 4s"));
    expect(screen.getByRole("button", { name: /grep/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("names the running step in plain words while it works", () => {
    const tools = [
      { tool_id: "a", name: "read_file", args: { path: "deploy.log" }, ok: true },
      { tool_id: "b", name: "web_fetch", args: { url: "status.example.com" }, ok: null },
    ];
    render(<ToolModule tools={tools} />);
    expect(line()).toHaveAccessibleName("Working · Fetching status.example.com");
    expect(line()).toHaveAttribute("data-work-state", "running");
  });

  it("says Thinking while the model thinks after its last step", () => {
    const tools = [{ tool_id: "a", name: "grep", args: {}, ok: true }];
    render(<ToolModule tools={tools} thinking />);
    expect(line()).toHaveAccessibleName("Working · Thinking");
  });

  it("leads with the profile's mark at the row size, working while it runs and idle once done", () => {
    const running = render(<ToolModule tools={[{ tool_id: "a", name: "grep", args: {}, ok: null }]} shape="bell" accent="#3899e2" />);
    const mark = running.container.querySelector("button [data-shape]");
    expect(mark.dataset.shape).toBe("bell");
    expect(mark.getAttribute("width") ?? mark.style.width).toMatch(/24/);
    running.unmount();
    render(<ToolModule tools={[{ tool_id: "a", name: "grep", args: {}, ok: true }]} shape="bell" accent="#3899e2" />);
    expect(line()).toHaveAttribute("data-work-state", "done");
  });

  it("keeps a step the user opened open when the next call starts", () => {
    const first = { tool_id: "a", name: "read_file", args: { path: "a" }, ok: null };
    const { rerender } = render(<ToolModule tools={[first]} />);
    fireEvent.click(line());
    fireEvent.click(screen.getByRole("button", { name: /read_file/ }));
    rerender(<ToolModule tools={[{ ...first, ok: true }, { tool_id: "b", name: "grep", args: {}, ok: null }]} />);
    expect(screen.getByRole("button", { name: /read_file/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /grep/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("never counts an empty sub-second stored span as a step", () => {
    const tools = [
      { tool_id: "a", name: "grep", args: {}, ok: true },
      { tool_id: "b", name: "read_file", args: {}, ok: true },
    ];
    render(<ProcessBlock entries={processTimeline(tools, "", 2, [{ seconds: 0.4, before_tool: 1 }])} />);
    expect(line().getAttribute("aria-label")).toMatch(/· 2 steps$/);
  });

  it("renders nothing when there is no process", () => {
    const { container } = render(<ToolModule tools={[]} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("process block typography", () => {
  const read = (rel) => readFileSync(join(import.meta.dirname, rel), "utf8");
  const block = (css, sel) => css.match(new RegExp(`\\.${sel} \\{([^}]+)\\}`))[1];
  const steps = read("ToolSteps.module.css");
  const reasoning = read("../primitives/Reasoning.module.css");

  it("leads the thinking row in sans at the same 32 px height, under the profile's object", () => {
    const rule = block(reasoning, "row");
    expect(rule).toMatch(/height: var\(--ctl-32\)/);
    expect(rule).toMatch(/font-family: var\(--font-sans\)/);
  });

  it.each([[steps, "head"]])("every tool row is a 14 px sans line of 32 px", (css, sel) => {
    const rule = block(css, sel);
    expect(rule).toMatch(/height: var\(--ctl-32\)/);
    expect(rule).toMatch(/font-family: var\(--font-sans\)/);
    expect(rule).toMatch(/font-size: var\(--text-small\)/);
  });

  it("sets only the tool's machine name in mono", () => {
    expect(block(steps, "name")).toMatch(/font-family: var\(--font-mono\)/);
    expect(block(steps, "name")).toMatch(/font-size: var\(--text-mono\)/);
  });

  it("labels and meta read ink-3, names ink-2, the opened thought sans ink-2", () => {
    expect(block(steps, "summary")).toMatch(/color: var\(--ink-3\)/);
    expect(block(steps, "status")).toMatch(/color: var\(--ink-3\)/);
    expect(block(steps, "name")).toMatch(/color: var\(--ink-2\)/);
    expect(block(reasoning, "label")).toMatch(/color: var\(--ink-3\)/);
    const para = block(reasoning, "para");
    expect(para).toMatch(/font-family: var\(--font-sans\)/);
    expect(para).toMatch(/font-size: var\(--text-small\)/);
    expect(para).toMatch(/color: var\(--ink-2\)/);
    expect(block(steps, "module")).toMatch(/gap: var\(--space-tight\)/);
  });

  it.each([[steps, "head"], [steps, "workLine"], [reasoning, "row"]])("pulls each row into the gutter by its own padding so glyphs sit flush with the answer", (css, sel) => {
    const rule = block(css, sel);
    expect(rule).toMatch(/margin: 0 calc\(-1 \* var\(--sp-12\)\)/);
    expect(rule).toMatch(/padding: 0 var\(--sp-12\)/);
    expect(rule).toMatch(/width: calc\(100% \+ 2 \* var\(--sp-12\)\)/);
  });

  it("keeps the opened bodies' indent relative to the row and indents the steps under the mark, with no rule", () => {
    expect(block(steps, "detail")).toMatch(/padding: var\(--sp-8\) 0 var\(--sp-8\) calc\(var\(--icon-sm\) \+ var\(--sp-12\)\)/);
    expect(block(reasoning, "body")).toMatch(/margin: var\(--sp-4\) 0 var\(--sp-4\) calc\(var\(--sp-16\) - var\(--sp-12\)\)/);
    expect(block(steps, "workReveal")).toMatch(/margin: 0 calc\(-1 \* var\(--sp-12\)\)/);
    expect(block(steps, "workRail")).toMatch(/padding: var\(--space-tight\) var\(--sp-12\) 0 calc\(var\(--sp-24\) \+ var\(--sp-12\)\)/);
    expect(block(steps, "workRail")).not.toMatch(/border/);
  });

  it("sets the work line in 15 px sans, the lead in ink, the detail in ink-3", () => {
    expect(block(steps, "workLine")).toMatch(/font-size: var\(--text-ui\)/);
    expect(block(steps, "workLead")).toMatch(/color: var\(--ink\)/);
    expect(block(steps, "workDetail")).toMatch(/color: var\(--ink-3\)/);
  });
});

describe("ProcessBlock hands the profile to its reasoning", () => {
  it("leads the opened thinking row with the profile's mark in its colour", () => {
    render(<ProcessBlock entries={[{ kind: "reasoning", key: "r0", text: "plan", seconds: 3 }]} shape="bell" accent="#3899e2" />);
    fireEvent.click(screen.getByRole("button", { name: /^Worked/ }));
    const marks = document.querySelectorAll("[data-shape]");
    expect(marks[marks.length - 1].dataset.shape).toBe("bell");
    expect(marks[marks.length - 1].querySelector("path[data-body]").getAttribute("fill")).toBe("#3899e2");
  });
});

describe("work line while the turn runs", () => {
  it("stays Working between rounds, when no tool runs and the model is not streaming reasoning", () => {
    render(<ToolModule tools={[{ tool_id: "a", name: "read_file", args: { path: "a" }, ok: true }]} running />);
    expect(screen.getByRole("button", { name: /^Working/ })).toHaveAccessibleName("Working · Thinking");
    expect(screen.getByRole("status")).toHaveTextContent("Thinking");
  });

  it("counts the clock from the earliest tool start in whole seconds, and stops once done", () => {
    vi.useFakeTimers();
    vi.setSystemTime(100_000);
    const tools = [{ tool_id: "a", name: "grep", args: {}, ok: null, started_at: 90 }];
    const { rerender, container } = render(<ToolModule tools={tools} running />);
    expect(container.textContent).toContain("10s");
    act(() => vi.advanceTimersByTime(3000));
    expect(container.textContent).toContain("13s");
    rerender(<ToolModule tools={[{ ...tools[0], ok: true, duration_s: 4 }]} />);
    expect(screen.getByRole("button", { name: /^Worked/ })).toHaveAccessibleName("Worked for 4s · 1 step");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("reports the wall span of the tools once done, not their summed durations", () => {
    const tools = [
      { tool_id: "a", name: "grep", args: {}, ok: true, started_at: 10, duration_s: 5 },
      { tool_id: "b", name: "read_file", args: {}, ok: true, started_at: 11, duration_s: 5 },
      { tool_id: "c", name: "terminal", args: {}, ok: true, started_at: 30, duration_s: 2 },
    ];
    render(<ToolModule tools={tools} />);
    expect(screen.getByRole("button", { name: /^Worked/ })).toHaveAccessibleName("Worked for 22s · 3 steps");
  });

  it("says Writing while the model streams text before its next step, and stays Working", () => {
    render(<ToolModule tools={[{ tool_id: "a", name: "grep", args: {}, ok: true }]} running writing />);
    expect(screen.getByRole("button", { name: /^Working/ })).toHaveAccessibleName("Working · Writing");
  });

  it("keeps the status region mounted and hands it the settled line once done", () => {
    const tools = [{ tool_id: "a", name: "grep", args: {}, ok: null }];
    const { rerender } = render(<ToolModule tools={tools} running />);
    const status = screen.getByRole("status");
    rerender(<ToolModule tools={[{ ...tools[0], ok: true, duration_s: 2 }]} />);
    expect(screen.getByRole("status")).toBe(status);
    expect(status).toHaveTextContent("Worked for 2s · 1 step");
  });

  it("stays open when the streaming turn becomes a history turn with the same memory key", () => {
    const tools = [{ tool_id: "a", name: "grep", args: {}, ok: null }];
    const first = render(<ToolModule tools={tools} running memoryKey="local|doc|what moved?" />);
    fireEvent.click(screen.getByRole("button", { name: /^Working/ }));
    first.unmount();
    render(<ToolModule tools={[{ ...tools[0], ok: true, duration_s: 1 }]} memoryKey="local|doc|what moved?" />);
    expect(screen.getByRole("button", { name: /^Worked/ })).toHaveAttribute("aria-expanded", "true");
  });

  it("carries the open state from a new chat's pending turn to its history turn, and not to another session", () => {
    const tools = [{ tool_id: "a", name: "grep", args: {}, ok: null }];
    const pending = render(<ToolModule tools={tools} running memoryKey={workLineKeys("local", "doc", null, 3, "hi")} />);
    fireEvent.click(screen.getByRole("button", { name: /^Working/ }));
    pending.unmount();
    const done = [{ ...tools[0], ok: true, duration_s: 1 }];
    const history = render(<ToolModule tools={done} memoryKey={workLineKeys("local", "doc", "s-1", 3, "hi")} />);
    expect(screen.getByRole("button", { name: /^Worked/ })).toHaveAttribute("aria-expanded", "true");
    history.unmount();
    render(<ToolModule tools={done} memoryKey={workLineKeys("local", "doc", "s-2", 3, "hi")} />);
    expect(screen.getByRole("button", { name: /^Worked/ })).toHaveAttribute("aria-expanded", "false");
  });
});

