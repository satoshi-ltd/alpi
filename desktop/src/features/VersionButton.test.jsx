import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";

const h = vi.hoisted(() => ({
  listener: null,
  state: {
    checking: false,
    available: false,
    version: null,
    error: null,
    errorPhase: null,
    installing: false,
    phase: "idle",
    progress: null,
  },
  checkForUpdates: vi.fn(),
  applyPendingUpdate: vi.fn(async () => true),
  quitForUpdate: vi.fn(async () => {}),
}));

vi.mock("../lib/updater.js", async () => {
  const real = await vi.importActual("../lib/updater.js");
  return {
    describeUpdaterError: real.describeUpdaterError,
    subscribeUpdater: (fn) => {
      h.listener = fn;
      fn(h.state);
      return () => {};
    },
    checkForUpdates: h.checkForUpdates,
    applyPendingUpdate: h.applyPendingUpdate,
    quitForUpdate: h.quitForUpdate,
  };
});

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(async () => {}) }));
vi.mock("@tauri-apps/api/event", () => ({ listen: vi.fn(async () => () => {}) }));
vi.mock("@tauri-apps/plugin-updater", () => ({ check: vi.fn() }));
vi.mock("@tauri-apps/plugin-process", () => ({ relaunch: vi.fn(), exit: vi.fn() }));

import VersionButton from "./VersionButton.jsx";

function push(patch) {
  h.state = { ...h.state, ...patch };
  act(() => h.listener?.(h.state));
}

beforeEach(() => {
  h.listener = null;
  h.state = { checking: false, available: false, version: null, error: null, errorPhase: null, installing: false, phase: "idle", progress: null };
  h.checkForUpdates.mockClear();
  h.applyPendingUpdate.mockClear();
});

describe("VersionButton", () => {
  it("offers the update and starts the install from the popover", () => {
    render(<VersionButton />);
    push({ available: true, version: "0.6.3" });
    fireEvent.click(screen.getByText("0.0.0"));
    expect(h.checkForUpdates).toHaveBeenCalled();
    expect(screen.getByText("Update available")).toBeTruthy();
    fireEvent.click(screen.getByText("Restart & install"));
    expect(h.applyPendingUpdate).toHaveBeenCalledTimes(1);
  });

  it("shows the download progress while it installs and opens by itself when the tray starts it", () => {
    render(<VersionButton />);
    push({ available: true, version: "0.6.3", installing: true, phase: "downloading", progress: 0.42 });
    expect(screen.getByText("Downloading… 42%")).toBeTruthy();
    push({ phase: "installing", progress: 1 });
    expect(screen.getByText("Installing…", { selector: "span" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Installing…" }).disabled).toBe(true);
  });

  it("keeps the update on offer after a failed download and says what went wrong", () => {
    render(<VersionButton />);
    push({ available: true, version: "0.6.3" });
    fireEvent.click(screen.getByText("0.0.0"));
    push({ installing: false, phase: "idle", error: "Download request failed with status 404", errorPhase: "install" });
    expect(screen.getByRole("alert").textContent).toBe("The update file is missing on the server");
    expect(screen.getByText("Try again")).toBeTruthy();
    fireEvent.click(screen.getByText("Try again"));
    expect(h.applyPendingUpdate).toHaveBeenCalledTimes(1);
  });

  it("offers Quit instead of another download once the update is installed but the relaunch failed", () => {
    render(<VersionButton />);
    push({ available: true, version: "0.6.3" });
    fireEvent.click(screen.getByText("0.0.0"));
    push({ installing: false, phase: "installed", error: "relaunch denied", errorPhase: "restart" });
    expect(screen.getByRole("alert").textContent).toBe("Update installed — quit and reopen Alpi to finish");
    expect(screen.queryByText("Try again")).toBeNull();
    fireEvent.click(screen.getByText("Quit Alpi"));
    expect(h.quitForUpdate).toHaveBeenCalledTimes(1);
    expect(h.applyPendingUpdate).not.toHaveBeenCalled();
  });

  it("mentions a check that failed after an update was found", () => {
    render(<VersionButton />);
    push({ available: true, version: "0.6.3" });
    fireEvent.click(screen.getByText("0.0.0"));
    push({ error: "Network Error", errorPhase: "check" });
    expect(screen.getByText("Update available")).toBeTruthy();
    expect(screen.getByText(/last check failed/).textContent).toMatch("Couldn't reach update server");
  });

  it("names a failed check without pretending the download failed", () => {
    render(<VersionButton />);
    fireEvent.click(screen.getByText("0.0.0"));
    push({ error: "Network Error", errorPhase: "check" });
    expect(screen.getByText("Couldn't reach update server")).toBeTruthy();
  });
});
