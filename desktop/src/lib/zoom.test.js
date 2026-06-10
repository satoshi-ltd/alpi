import { describe, it, expect, vi } from "vitest";

vi.mock("@tauri-apps/api/webview", () => ({
  getCurrentWebview: () => ({ setZoom: vi.fn(async () => {}) }),
}));

const { clampZoom, nextZoom } = await import("./zoom.js");

describe("zoom steps and limits", () => {
  it("steps up by 0.1 and caps at 1.5", () => {
    expect(nextZoom(1, 1)).toBe(1.1);
    expect(nextZoom(1.4, 1)).toBe(1.5);
    expect(nextZoom(1.5, 1)).toBe(1.5);
  });

  it("steps down by 0.1 and floors at 0.7", () => {
    expect(nextZoom(1, -1)).toBe(0.9);
    expect(nextZoom(0.8, -1)).toBe(0.7);
    expect(nextZoom(0.7, -1)).toBe(0.7);
  });

  it("direction 0 resets to 1 from anywhere", () => {
    expect(nextZoom(1.5, 0)).toBe(1);
    expect(nextZoom(0.7, 0)).toBe(1);
  });

  it("avoids float drift across repeated steps", () => {
    let z = 1;
    for (let i = 0; i < 3; i += 1) z = nextZoom(z, -1);
    expect(z).toBe(0.7);
    for (let i = 0; i < 8; i += 1) z = nextZoom(z, 1);
    expect(z).toBe(1.5);
  });

  it("clamps garbage to 1 and out-of-range to the limits", () => {
    expect(clampZoom("nope")).toBe(1);
    expect(clampZoom(99)).toBe(1.5);
    expect(clampZoom(0.1)).toBe(0.7);
  });
});
