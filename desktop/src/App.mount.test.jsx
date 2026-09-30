import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

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
  it("mounts with an unreachable daemon without throwing", () => {
    render(<App />);
    expect(screen.getAllByRole("complementary").length).toBeGreaterThan(0);
  });
});
