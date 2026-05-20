import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { formatRelative, formatClock } from "./format.js";

const REF = new Date("2026-05-20T12:00:00Z").getTime();

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(REF);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("formatRelative", () => {
  it("falsy epoch → empty", () => {
    expect(formatRelative(0)).toBe("");
    expect(formatRelative(undefined)).toBe("");
  });

  it("< 60s → just now", () => {
    expect(formatRelative((REF - 30 * 1000) / 1000)).toBe("just now");
  });

  it("minutes / hours / days bands", () => {
    expect(formatRelative((REF - 5 * 60 * 1000) / 1000)).toBe("5m ago");
    expect(formatRelative((REF - 3 * 3600 * 1000) / 1000)).toBe("3h ago");
    expect(formatRelative((REF - 2 * 86400 * 1000) / 1000)).toBe("2d ago");
  });

  it("≥7d falls back to absolute date", () => {
    const out = formatRelative((REF - 8 * 86400 * 1000) / 1000);
    // Different locales / runners format slightly differently; just make sure
    // it isn't one of the relative-band strings.
    expect(out).not.toMatch(/ago|just now/);
    expect(out.length).toBeGreaterThan(0);
  });
});

describe("formatClock", () => {
  it("returns a HH:MM-ish string for an epoch", () => {
    const out = formatClock((REF - 60 * 1000) / 1000);
    expect(out).toMatch(/\d{1,2}:\d{2}/);
  });

  it("falsy / NaN → empty", () => {
    expect(formatClock(0)).toBe("");
    expect(formatClock("not-a-date")).toBe("");
  });
});
