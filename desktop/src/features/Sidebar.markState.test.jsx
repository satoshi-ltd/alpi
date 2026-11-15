import { describe, it, expect, vi } from "vitest";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

vi.mock("../lib/updater.js", () => ({
  describeUpdaterError: () => "",
  quitForUpdate: vi.fn(),
  applyPendingUpdate: vi.fn(),
  checkForUpdates: vi.fn(),
  subscribeUpdater: vi.fn(() => () => {}),
}));

import { profileMarkState } from "./Sidebar.jsx";

describe("profileMarkState", () => {
  it("reads needs you over the session's done or failed on the selected row", () => {
    expect(profileMarkState({ rowState: "needs-you", live: "done" })).toBe("needs");
    expect(profileMarkState({ rowState: "needs-you", live: "failed" })).toBe("needs");
    expect(profileMarkState({ rowState: "needs-you", live: "working" })).toBe("needs");
  });

  it("orders needs over failed over working", () => {
    expect(profileMarkState({ rowState: "needs-you", pending: true })).toBe("needs");
    expect(profileMarkState({ rowState: "failed", pending: true })).toBe("failed");
    expect(profileMarkState({ rowState: "working" })).toBe("working");
    expect(profileMarkState({ pending: true })).toBe("working");
  });

  it("keeps a missing provider and a pause above every row state", () => {
    expect(profileMarkState({ incomplete: true, rowState: "failed", live: "done" })).toBe("needs");
    expect(profileMarkState({ paused: true, rowState: "needs-you", live: "working" })).toBe("paused");
  });

  it("reads paused over a missing provider, like the session mark and mobile", () => {
    expect(profileMarkState({ paused: true, incomplete: true })).toBe("paused");
    expect(profileMarkState({ paused: true, incomplete: true, rowState: "needs-you" })).toBe("paused");
  });

  it("lets the open session's live state lead the other row states", () => {
    expect(profileMarkState({ rowState: "failed", live: "done" })).toBe("done");
    expect(profileMarkState({ rowState: "working", live: "failed" })).toBe("failed");
    expect(profileMarkState({ rowState: "failed", live: "idle" })).toBe("failed");
    expect(profileMarkState({ unread: true })).toBe("done");
    expect(profileMarkState({})).toBe("idle");
  });
});
