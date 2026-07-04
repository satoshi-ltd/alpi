import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());

const profile = { name: "a", model: "prov/base" };

function renderPane({ sessionData, sessionSync = null, onRewriteMessage = vi.fn() }) {
  return render(
    <ChatPane
      view={{ kind: "profile", profile: "a", sessionId: "s1" }}
      profiles={[profile]}
      activeProfile={profile}
      sessionData={sessionData}
      sessionSync={sessionSync}
      onSend={vi.fn()}
      onRewriteMessage={onRewriteMessage}
      onRetryMessage={vi.fn()}
    />,
  );
}

const turnsData = {
  id: "s1",
  turns: [{ at: 1, user: "hello", assistant: "world" }],
  last_ctx_tokens: 0,
};

describe("ChatPane — sync indicators", () => {
  it("shows the controlled refresh bar and backfill pill after the anti-flash delay", () => {
    renderPane({
      sessionData: { ...turnsData, turnsOffset: 120, totalTurns: 121, partialTail: true },
      sessionSync: { phase: "backfill", loaded: 1, total: 121 },
    });
    expect(screen.queryByRole("progressbar", { name: "syncing conversation" })).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
    act(() => vi.advanceTimersByTime(450));
    expect(screen.getByRole("progressbar", { name: "syncing conversation" })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("syncing history · 1/121");
  });

  it("shows a plain syncing pill during the refresh phase over stale data", () => {
    renderPane({ sessionData: turnsData, sessionSync: { phase: "refresh" } });
    act(() => vi.advanceTimersByTime(450));
    expect(screen.getByRole("status").textContent).toContain("syncing…");
  });

  it("hides every indicator when sync is idle", () => {
    renderPane({ sessionData: turnsData, sessionSync: null });
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.queryByRole("progressbar", { name: "syncing conversation" })).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("never shows the pill without data (skeleton owns that state)", () => {
    renderPane({ sessionData: null, sessionSync: { phase: "refresh" } });
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("ChatPane — partial transcripts use absolute turn indices", () => {
  it("reports the rewrite index offset by turnsOffset", () => {
    const onRewriteMessage = vi.fn();
    renderPane({
      sessionData: { ...turnsData, turnsOffset: 200, totalTurns: 201, partialTail: true },
      onRewriteMessage,
    });
    fireEvent.click(screen.getByLabelText("Edit message"));
    expect(onRewriteMessage).toHaveBeenCalledWith("a", "s1", 200, "hello");
  });

  it("keeps plain indices for full transcripts", () => {
    const onRewriteMessage = vi.fn();
    renderPane({ sessionData: turnsData, onRewriteMessage });
    fireEvent.click(screen.getByLabelText("Edit message"));
    expect(onRewriteMessage).toHaveBeenCalledWith("a", "s1", 0, "hello");
  });
});
