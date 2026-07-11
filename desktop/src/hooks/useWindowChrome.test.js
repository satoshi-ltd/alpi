import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useWindowChrome } from "./useWindowChrome.js";

vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: () => ({
    startDragging: vi.fn(async () => {}),
    toggleMaximize: vi.fn(async () => {}),
  }),
}));

function press(key, options = {}) {
  window.dispatchEvent(new KeyboardEvent("keydown", {
    key,
    bubbles: true,
    cancelable: true,
    ...options,
  }));
}

function mountWindowChrome(overrides = {}) {
  const props = {
    viewRef: { current: { kind: "settings" } },
    setView: vi.fn(),
    paletteOpenRef: { current: false },
    activeProfileName: "doc",
    historyKind: "sessions",
    onOpenHistory: vi.fn(),
    onRefreshThread: vi.fn(),
    onToggleContextPause: vi.fn(),
    onToggleReadAloud: vi.fn(),
    onBrowseTools: vi.fn(),
    onBrowseSkills: vi.fn(),
    onBrowseMemory: vi.fn(),
    onBrowseSchedule: vi.fn(),
    onToggleNotifications: vi.fn(),
    ...overrides,
  };
  const hook = renderHook(() => useWindowChrome(props));
  return { ...props, unmount: hook.unmount };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useWindowChrome", () => {
  it("opens profile browse modals from settings when a profile is active", () => {
    const chrome = mountWindowChrome();

    press("S", { metaKey: true, shiftKey: true });
    press("M", { metaKey: true, shiftKey: true });
    press("T", { metaKey: true, shiftKey: true });
    press("E", { metaKey: true, shiftKey: true });

    expect(chrome.onBrowseSkills).toHaveBeenCalledTimes(1);
    expect(chrome.onBrowseMemory).toHaveBeenCalledTimes(1);
    expect(chrome.onBrowseTools).toHaveBeenCalledTimes(1);
    expect(chrome.onBrowseSchedule).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("ignores profile browse shortcuts without an active profile", () => {
    const chrome = mountWindowChrome({ activeProfileName: null });

    press("S", { metaKey: true, shiftKey: true });

    expect(chrome.onBrowseSkills).not.toHaveBeenCalled();
    chrome.unmount();
  });

  it("opens notifications from any view", () => {
    const chrome = mountWindowChrome({ activeProfileName: null });

    press("o", { metaKey: true });

    expect(chrome.onToggleNotifications).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("does not reserve command slash for a separate shortcuts modal", () => {
    const chrome = mountWindowChrome({ activeProfileName: null });

    press("/", { metaKey: true });

    expect(chrome.onToggleNotifications).not.toHaveBeenCalled();
    expect(chrome.onOpenHistory).not.toHaveBeenCalled();
    chrome.unmount();
  });

  it("opens contextual history when available", () => {
    const chrome = mountWindowChrome({ historyKind: "tasks" });

    press("H", { metaKey: true, shiftKey: true });

    expect(chrome.onOpenHistory).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("toggles read aloud with shift command l", () => {
    const chrome = mountWindowChrome();

    press("L", { metaKey: true, shiftKey: true });

    expect(chrome.onToggleReadAloud).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("refreshes the active thread with shift command r", () => {
    const chrome = mountWindowChrome();

    press("R", { metaKey: true, shiftKey: true });

    expect(chrome.onRefreshThread).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("toggles the active pause state with shift command p", () => {
    const chrome = mountWindowChrome();

    press("P", { metaKey: true, shiftKey: true });

    expect(chrome.onToggleContextPause).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("ignores contextual history when no history target exists", () => {
    const chrome = mountWindowChrome({ historyKind: null });

    press("H", { metaKey: true, shiftKey: true });

    expect(chrome.onOpenHistory).not.toHaveBeenCalled();
    chrome.unmount();
  });
});
