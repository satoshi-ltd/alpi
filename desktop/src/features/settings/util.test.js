import { describe, it, expect, vi, afterEach } from "vitest";

import { formatLastRun, providerPills } from "./util.js";

afterEach(() => {
  vi.useRealTimers();
});

describe("formatLastRun", () => {
  it("returns 'never run' without an execution status, even if last_run_at is set (cron anchor)", () => {
    expect(formatLastRun(null, undefined)).toBe("never run");
    expect(formatLastRun("2026-07-02T10:00:00Z", undefined)).toBe("never run");
    expect(formatLastRun("2026-07-02T10:00:00Z", null)).toBe("never run");
    expect(formatLastRun("not-a-date", "ok")).toBe("never run");
  });

  it("formats a successful run as a relative 'ran …' label", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-02T12:00:00Z"));
    expect(formatLastRun("2026-07-02T10:00:00Z", "ok")).toBe("ran 2h ago");
    expect(formatLastRun("2026-07-02T11:59:30Z", "ok")).toBe("ran just now");
  });

  it("flags a failed run distinctly", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-02T12:00:00Z"));
    expect(formatLastRun("2026-07-02T10:00:00Z", "error")).toBe("last run failed · 2h ago");
  });
});

describe("providerPills", () => {
  it("maps cloud keys and ollama servers to labeled pills", () => {
    const profile = {
      provider_keys: [{ env: "OPENROUTER_API_KEY" }, { env: "ANTHROPIC_API_KEY" }],
      provider_ollama: [{ name: "home-mbp", url: "http://localhost:11434" }],
    };
    expect(providerPills(profile)).toEqual([
      { label: "openrouter", error: null },
      { label: "anthropic", error: null },
      { label: "ollama/home-mbp", error: null },
    ]);
  });

  it("attaches the failure detail to the matching ollama pill only", () => {
    const profile = {
      provider_keys: [{ env: "OPENROUTER_API_KEY" }],
      provider_ollama: [
        { name: "home-mbp", url: "http://localhost:11434" },
        { name: "atlas", url: "http://100.99.29.84:11434" },
      ],
    };
    const errors = [{
      name: "home-mbp",
      url: "http://localhost:11434",
      detail: "[Errno 61] Connection refused",
    }];
    const pills = providerPills(profile, errors);
    expect(pills.find((p) => p.label === "ollama/home-mbp").error)
      .toBe("http://localhost:11434 — [Errno 61] Connection refused");
    expect(pills.find((p) => p.label === "ollama/atlas").error).toBeNull();
    expect(pills.find((p) => p.label === "openrouter").error).toBeNull();
  });

  it("handles profiles without providers", () => {
    expect(providerPills({})).toEqual([]);
  });
});
