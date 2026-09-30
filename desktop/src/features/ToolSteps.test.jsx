import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import { ToolModule, ToolStep } from "./ToolSteps.jsx";

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

describe("ToolModule", () => {
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
});
