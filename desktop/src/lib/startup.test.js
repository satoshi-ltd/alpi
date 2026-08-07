import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

import { clearCrash, readCrash } from "./crashLog.js";
import { startApp } from "./startup.js";

beforeEach(() => {
  clearCrash();
  document.body.innerHTML = '<div id="root"></div>';
});

describe("desktop startup", () => {
  it("renders a report when the dynamically loaded application fails", async () => {
    await startApp(() => Promise.reject(new Error("module evaluation failed")));
    expect(screen.getByText("Alpi failed to start")).toBeTruthy();
    expect(screen.getByText(/module evaluation failed/)).toBeTruthy();
    expect(readCrash()).toMatchObject({
      phase: "bootstrap",
      message: "module evaluation failed",
    });
  });

  it("starts the loaded application after installing global handlers", async () => {
    const bootstrap = vi.fn();
    await startApp(async () => {
      expect(window.__alpiCrashHandlers).toBe(true);
      return { bootstrap };
    });
    expect(bootstrap).toHaveBeenCalledOnce();
  });

  it("catches clipboard rejection without replacing the startup report", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("clipboard denied"));
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    await startApp(() => Promise.reject(new Error("module evaluation failed")));
    fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
    expect(await screen.findByRole("button", { name: "Copy failed — select details" })).toBeTruthy();
    expect(readCrash()).toMatchObject({
      phase: "bootstrap",
      message: "module evaluation failed",
    });
  });
});
