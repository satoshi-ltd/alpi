// Tauri API mocks live in tests/__mocks__/tauri.js and are imported per-test.
// Keep this file minimal: jest-dom matchers + a safe default for invoke/listen.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
});

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(async () => null),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(async () => () => {}),
  emit: vi.fn(async () => {}),
}));

vi.mock("@tauri-apps/api/app", () => ({
  getVersion: vi.fn(async () => "0.3.4-test"),
  getTauriVersion: vi.fn(async () => "2.0-test"),
}));
