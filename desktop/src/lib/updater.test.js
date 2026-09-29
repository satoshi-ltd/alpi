import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({
  check: vi.fn(),
  relaunch: vi.fn(async () => {}),
  exit: vi.fn(async () => {}),
  invoke: vi.fn(async () => {}),
  listen: vi.fn(async () => () => {}),
}));

vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));
vi.mock("@tauri-apps/api/event", () => ({ listen: h.listen }));
vi.mock("@tauri-apps/plugin-updater", () => ({ check: h.check }));
vi.mock("@tauri-apps/plugin-process", () => ({ relaunch: h.relaunch, exit: h.exit }));

import {
  _resetUpdaterForTests,
  applyPendingUpdate,
  checkForUpdates,
  describeUpdaterError,
  quitForUpdate,
  subscribeUpdater,
} from "./updater.js";

function found(downloadAndInstall) {
  return { available: true, version: "0.6.3", downloadAndInstall };
}

function states() {
  const seen = [];
  subscribeUpdater((s) => seen.push(s));
  return seen;
}

beforeEach(() => {
  _resetUpdaterForTests();
  h.check.mockReset();
  h.relaunch.mockClear();
  h.invoke.mockClear();
});

describe("checkForUpdates", () => {
  it("records an available update and tells the tray", async () => {
    h.check.mockResolvedValueOnce(found(vi.fn()));
    const s = await checkForUpdates();
    expect(s).toMatchObject({ available: true, version: "0.6.3", checking: false, error: null });
    expect(h.invoke).toHaveBeenCalledWith("tray_announce_update", { available: true, version: "0.6.3" });
  });

  it("keeps an update it already found when a later check fails", async () => {
    h.check.mockResolvedValueOnce(found(vi.fn()));
    await checkForUpdates();
    h.check.mockRejectedValueOnce(new Error("Network Error: dns"));
    const s = await checkForUpdates();
    expect(s).toMatchObject({ available: true, version: "0.6.3", errorPhase: "check" });
    expect(s.error).toMatch("dns");
  });
});

describe("applyPendingUpdate", () => {
  it("reports download progress, then installs and relaunches", async () => {
    const dl = vi.fn(async (onEvent) => {
      onEvent({ event: "Started", data: { contentLength: 200 } });
      onEvent({ event: "Progress", data: { chunkLength: 50 } });
      onEvent({ event: "Progress", data: { chunkLength: 150 } });
      onEvent({ event: "Finished" });
    });
    h.check.mockResolvedValueOnce(found(dl));
    await checkForUpdates();
    const seen = states();
    await expect(applyPendingUpdate()).resolves.toBe(true);
    const phases = seen.map((s) => `${s.phase}:${s.progress}`);
    expect(phases).toContain("downloading:0.25");
    expect(phases).toContain("downloading:1");
    expect(phases).toContain("installing:1");
    expect(phases).toContain("restarting:1");
    expect(h.relaunch).toHaveBeenCalledTimes(1);
  });

  it("keeps the update offered and names the failure when the download 404s", async () => {
    const dl = vi.fn(async () => {
      throw new Error("Download request failed with status 404");
    });
    h.check.mockResolvedValueOnce(found(dl));
    await checkForUpdates();
    await expect(applyPendingUpdate()).rejects.toThrow("404");
    const seen = states();
    expect(seen[0]).toMatchObject({ available: true, version: "0.6.3", installing: false, phase: "idle", errorPhase: "install" });
    expect(describeUpdaterError(seen[0].error, seen[0].errorPhase)).toBe("The update file is missing on the server");
    expect(h.relaunch).not.toHaveBeenCalled();
  });

  it("runs one install at a time and does nothing without a pending update", async () => {
    await expect(applyPendingUpdate()).resolves.toBe(false);
    let release;
    const dl = vi.fn(() => new Promise((resolve) => { release = resolve; }));
    h.check.mockResolvedValueOnce(found(dl));
    await checkForUpdates();
    const first = applyPendingUpdate();
    const second = applyPendingUpdate();
    expect(second).toBe(first);
    expect(await checkForUpdates()).toMatchObject({ installing: true });
    expect(h.check).toHaveBeenCalledTimes(1);
    release();
    await first;
    expect(dl).toHaveBeenCalledTimes(1);
  });

  it("says the update is installed when only the relaunch fails, and quits on request", async () => {
    h.check.mockResolvedValueOnce(found(vi.fn(async () => {})));
    await checkForUpdates();
    h.relaunch.mockRejectedValueOnce(new Error("relaunch denied"));
    await expect(applyPendingUpdate()).rejects.toThrow("relaunch");
    const seen = states();
    expect(seen[0]).toMatchObject({ installing: false, phase: "installed", errorPhase: "restart" });
    expect(describeUpdaterError(seen[0].error, "restart")).toBe("Update installed — quit and reopen Alpi to finish");
    await quitForUpdate();
    expect(h.exit).toHaveBeenCalledWith(0);
  });

  it("refuses a second download while the relaunch is still pending", async () => {
    const dl = vi.fn(async () => {});
    h.check.mockResolvedValueOnce(found(dl));
    await checkForUpdates();
    let releaseRelaunch;
    h.relaunch.mockImplementationOnce(() => new Promise((resolve) => { releaseRelaunch = resolve; }));
    const first = applyPendingUpdate();
    await vi.waitFor(() => expect(h.relaunch).toHaveBeenCalledTimes(1));
    await expect(applyPendingUpdate()).resolves.toBe(false);
    releaseRelaunch();
    await first;
    expect(dl).toHaveBeenCalledTimes(1);
  });
});

describe("describeUpdaterError", () => {
  it("separates a failed check from a failed download", () => {
    expect(describeUpdaterError("Network Error", "check")).toBe("Couldn't reach update server");
    expect(describeUpdaterError("Network Error", "install")).toBe("Download interrupted — check your connection");
    expect(describeUpdaterError("no platform fallback", "check")).toBe("No build available for your platform yet");
    expect(describeUpdaterError("signature mismatch", "install")).toBe("Update signature check failed");
    expect(describeUpdaterError("boom", "install")).toBe("Couldn't install the update");
    expect(describeUpdaterError("boom")).toBe("Couldn't check for updates");
  });
});
