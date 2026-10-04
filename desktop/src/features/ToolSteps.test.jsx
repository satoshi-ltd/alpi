import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { ProcessBlock, ToolStep } from "./ToolSteps.jsx";
import { processTimeline } from "../lib/reasoningTimeline.js";

function ToolModule({ tools, reasoning, seconds, ...rest }) {
  return <ProcessBlock entries={processTimeline(tools, reasoning, seconds)} {...rest} />;
}

afterEach(() => {
  vi.useRealTimers();
});

describe("ToolStep", () => {
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

  it("starts a failed call expanded with its output", () => {
    render(<ToolStep tool={{ name: "terminal", args: { command: "npm run lint" }, ok: false, duration_s: 4.1, output: "1 error" }} />);
    expect(screen.getByRole("button", { name: /terminal/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("failed · 4.1s")).toBeTruthy();
    expect(screen.getByText("1 error")).toBeTruthy();
    expect(screen.getByText("Output")).toBeTruthy();
  });

  it("opens itself when a live call fails", () => {
    const { rerender } = render(<ToolStep tool={{ name: "terminal", args: {}, ok: null }} />);
    expect(screen.getByRole("button", { name: /terminal/ })).toHaveAttribute("aria-expanded", "false");
    rerender(<ToolStep tool={{ name: "terminal", args: {}, ok: false, output: "boom" }} />);
    expect(screen.getByRole("button", { name: /terminal/ })).toHaveAttribute("aria-expanded", "true");
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
  it("keeps a clean group collapsed until clicked", () => {
    const tools = [
      { tool_id: "a", name: "read_file", args: { path: "a" }, ok: true },
      { tool_id: "b", name: "grep", args: { pattern: "x" }, ok: true },
    ];
    render(<ToolModule tools={tools} />);
    expect(screen.getByText("2 tool calls")).toBeTruthy();
    expect(screen.queryByText("read_file")).toBeNull();
    fireEvent.click(screen.getByLabelText(/Show 2 tool calls/));
    expect(screen.getByText("read_file")).toBeTruthy();
  });

  it("opens the group when it holds a failure and shows that call expanded", () => {
    const tools = [
      { tool_id: "a", name: "read_file", args: { path: "a" }, ok: true },
      { tool_id: "b", name: "terminal", args: { command: "lint" }, ok: false, output: "1 error" },
    ];
    render(<ToolModule tools={tools} />);
    expect(screen.getByText("1 failed")).toBeTruthy();
    expect(screen.getByLabelText("Hide tool calls")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /terminal/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("1 error")).toBeTruthy();
  });

  it("keeps a step the user opened open and visible when the next call starts", () => {
    const first = { tool_id: "a", name: "read_file", args: { path: "a" }, ok: null };
    const { rerender } = render(<ToolModule tools={[first]} />);
    fireEvent.click(screen.getByRole("button", { name: /read_file/ }));
    rerender(<ToolModule tools={[{ ...first, ok: true }, { tool_id: "b", name: "grep", args: {}, ok: null }]} />);
    expect(screen.getByRole("button", { name: /read_file/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /grep/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("lays reasoning and steps out in the order they happened, thought first when it led", () => {
    const tools = [
      { tool_id: "a", name: "read_file", args: {}, ok: true, reasoning: "check the log", reasoned_s: 2 },
      { tool_id: "b", name: "grep", args: {}, ok: true },
    ];
    const { container } = render(<ToolModule tools={tools} reasoning={"check the log\n\nsummarize"} seconds={6} />);
    const text = container.textContent;
    expect(text.indexOf("Thought for 2s")).toBe(0);
    expect(text.indexOf("Thought for 2s")).toBeLessThan(text.indexOf("2 tool calls"));
    expect(text.indexOf("2 tool calls")).toBeLessThan(text.indexOf("Thought for 4s"));
  });

  it("keeps mid-run reasoning inside the bucket, between the steps", () => {
    const tools = [
      { tool_id: "a", name: "read_file", args: {}, ok: true },
      { tool_id: "b", name: "grep", args: {}, ok: true, reasoning: "narrow it" },
    ];
    const { container } = render(<ToolModule tools={tools} reasoning="narrow it" />);
    expect(screen.queryByText("Thought")).toBeNull();
    expect(screen.getByText("2 tool calls · 1 thought")).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/Show 2 tool calls/));
    const text = container.textContent;
    expect(text.indexOf("read_file")).toBeLessThan(text.indexOf("Thought"));
    expect(text.indexOf("Thought")).toBeLessThan(text.indexOf("grep"));
  });

  it("shows the running call with the thought that led to it outside the bucket", () => {
    const tools = [
      { tool_id: "a", name: "read_file", args: {}, ok: true },
      { tool_id: "b", name: "terminal", args: {}, ok: null, reasoning: "run the tests" },
    ];
    render(<ToolModule tools={tools} />);
    expect(screen.getByText("+1 previous tool call")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Thought" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /terminal/ })).toBeTruthy();
  });

  it("adds the live Thinking row at the end of the block", () => {
    const tools = [{ tool_id: "a", name: "grep", args: {}, ok: true }];
    const { container } = render(<ToolModule tools={tools} thinking />);
    const text = container.textContent;
    expect(text.indexOf("grep")).toBeLessThan(text.indexOf("Thinking…"));
  });

  it("keeps an opened live thought open when its tool starts", () => {
    const { rerender } = render(<ToolModule tools={[]} reasoning="plan it" thinking />);
    fireEvent.click(screen.getByRole("button", { name: /Thinking…/ }));
    rerender(<ToolModule tools={[{ tool_id: "a", name: "grep", args: {}, ok: null, reasoning: "plan it" }]} reasoning="" />);
    expect(screen.getByRole("button", { name: "Thought" })).toHaveAttribute("aria-expanded", "true");
  });

  it("never counts an empty sub-second stored span as a thought", () => {
    const tools = [
      { tool_id: "a", name: "grep", args: {}, ok: true },
      { tool_id: "b", name: "read_file", args: {}, ok: true },
    ];
    render(<ProcessBlock entries={processTimeline(tools, "", 2, [{ seconds: 0.4, before_tool: 1 }])} />);
    expect(screen.getByText("2 tool calls")).toBeTruthy();
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

  it("leads the thinking row in sans at the same 22 px height, under the profile's object", () => {
    const rule = block(reasoning, "row");
    expect(rule).toMatch(/height: var\(--ctrl-xs\)/);
    expect(rule).toMatch(/font-family: var\(--font-sans\)/);
  });

  it.each([[steps, "head"], [steps, "bucket"]])("every tool row is a 22 px mono 12 px line", (css, sel) => {
    const rule = block(css, sel);
    expect(rule).toMatch(/height: var\(--ctrl-xs\)/);
    expect(rule).toMatch(/font-family: var\(--font-mono\)/);
    expect(rule).toMatch(/font-size: var\(--fs-sm\)/);
  });

  it("labels and meta read ink-3, names ink-2, the opened thought mono ink-2", () => {
    expect(block(steps, "summary")).toMatch(/color: var\(--ink-3\)/);
    expect(block(steps, "status")).toMatch(/color: var\(--ink-3\)/);
    expect(block(steps, "name")).toMatch(/color: var\(--ink-2\)/);
    expect(block(reasoning, "label")).toMatch(/color: color-mix\(in srgb, var\(--c, var\(--ink-3\)\) 50%, var\(--ink\)\)/);
    const para = block(reasoning, "para");
    expect(para).toMatch(/font-family: var\(--font-mono\)/);
    expect(para).toMatch(/font-size: var\(--fs-sm\)/);
    expect(para).toMatch(/color: var\(--ink-2\)/);
    expect(block(steps, "module")).toMatch(/gap: var\(--space-tight\)/);
  });

  it.each([[steps, "head"], [steps, "bucket"], [reasoning, "row"]])("pulls each row into the gutter by its own padding so glyphs sit flush with the answer", (css, sel) => {
    const rule = block(css, sel);
    expect(rule).toMatch(/margin: 0 calc\(-1 \* var\(--space-4\)\)/);
    expect(rule).toMatch(/padding: 0 var\(--space-4\)/);
    expect(rule).toMatch(/width: calc\(100% \+ 2 \* var\(--space-4\)\)/);
  });

  it("keeps the opened bodies' indent relative to the row and lets the bucket's rows reach the gutter", () => {
    expect(block(steps, "detail")).toMatch(/padding: var\(--space-3\) 0 var\(--space-3\) calc\(14px \+ var\(--space-4\)\)/);
    expect(block(reasoning, "body")).toMatch(/margin: var\(--space-1\) 0 var\(--space-1\) calc\(var\(--space-6\) - var\(--space-4\)\)/);
    expect(block(steps, "bucketReveal")).toMatch(/margin: 0 calc\(-1 \* var\(--space-4\)\)/);
    expect(block(steps, "bucketList")).toMatch(/calc\(var\(--space-6\) \+ var\(--space-4\)\)/);
  });
});

describe("ProcessBlock hands the profile to its reasoning", () => {
  it("leads the thinking row with the profile's fold in its colour", () => {
    render(<ProcessBlock entries={[{ kind: "reasoning", key: "r0", text: "plan", seconds: 3 }]} fold="shield" accent="#3899e2" />);
    expect(document.querySelector("[data-fold]").dataset.fold).toBe("shield");
    expect(document.querySelector("[data-fold] polygon").getAttribute("fill")).toBeTruthy();
  });
});
