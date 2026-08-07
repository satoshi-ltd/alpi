import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import ErrorBoundary from "./ErrorBoundary.jsx";
import { clearCrash, formatCrash, readCrash, recordCrash } from "../lib/crashLog.js";

function Boom({ when = true }) {
  if (when) throw new Error("kaboom from render");
  return <div>fine</div>;
}

beforeEach(() => {
  clearCrash();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ErrorBoundary", () => {
  it("renders children while nothing throws", () => {
    render(
      <ErrorBoundary>
        <Boom when={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("fine")).toBeTruthy();
  });

  it("shows the error, the process boundary and both actions when a child throws", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something broke on screen")).toBeTruthy();
    expect(screen.getAllByText(/kaboom from render/).length).toBeGreaterThan(0);
    expect(screen.getByText(/unsaved interface changes/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reload" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Copy details" })).toBeTruthy();
  });

  it("keeps the stack behind a disclosure so the screen is not a wall of text", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    const summary = screen.getByText("Technical details");
    expect(summary.closest("details").open).toBe(false);
    expect(screen.getByText(/component stack:/)).toBeTruthy();
  });

  it("persists the crash so a reload does not lose the evidence", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    const entry = readCrash();
    expect(entry.message).toBe("kaboom from render");
    expect(entry.phase).toBe("render");
    expect(entry.componentStack).toContain("Boom");
    expect(formatCrash(entry)).toContain("kaboom from render");
  });

  it("copies the full report to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
    await vi.waitFor(() => expect(writeText).toHaveBeenCalled());
    const payload = writeText.mock.calls[0][0];
    expect(payload).toContain("kaboom from render");
    expect(payload).toContain("stack:");
    expect(await screen.findByRole("button", { name: "Copied to clipboard" })).toBeTruthy();
  });

  it("keeps the previous report available after reload until the user continues", () => {
    const previous = recordCrash(new Error("previous render failed"), { phase: "render" });
    render(
      <ErrorBoundary initialEntry={previous}>
        <div>healthy interface</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("Alpi recovered from a crash")).toBeTruthy();
    expect(screen.getByText("previous render failed")).toBeTruthy();
    expect(screen.queryByText("healthy interface")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByText("healthy interface")).toBeTruthy();
    expect(readCrash()).toBeNull();
  });

  it("reports a clipboard failure without replacing the stored crash", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("clipboard denied"));
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
    expect(await screen.findByRole("button", { name: "Copy failed" })).toBeTruthy();
    expect(readCrash().message).toBe("kaboom from render");
  });
});
