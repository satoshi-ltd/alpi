import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
window.matchMedia ??= () => ({
  matches: false,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
});

vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: () => ({ startDragging: vi.fn(async () => {}), toggleMaximize: vi.fn(async () => {}) }),
}));
vi.mock("./lib/updater.js", () => ({
  installUpdater: () => () => {},
  describeUpdaterError: () => "",
  quitForUpdate: vi.fn(),
  applyPendingUpdate: vi.fn(),
  checkForUpdates: vi.fn(),
  subscribeUpdater: vi.fn(() => () => {}),
}));

import App from "./App.jsx";

describe("App shell", () => {
  it("mounts with an unreachable daemon without throwing, as the bare first-run frame", () => {
    localStorage.clear();
    const { container } = render(<App />);
    expect(container.querySelector("aside")).toBeNull();
    expect(container.querySelectorAll("main [data-drag]")).toHaveLength(1);
  });

  it("mounts the sidebar at once for a returning user", () => {
    localStorage.setItem("alpi.localEverOnline.v1", "seen");
    const { container } = render(<App />);
    expect(container.querySelector("aside")).not.toBeNull();
    localStorage.clear();
  });
});
