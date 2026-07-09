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
    onBrowseTools: vi.fn(),
    onBrowseSkills: vi.fn(),
    onBrowseMemory: vi.fn(),
    onToggleNotifications: vi.fn(),
    onToggleShortcuts: vi.fn(),
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

    expect(chrome.onBrowseSkills).toHaveBeenCalledTimes(1);
    expect(chrome.onBrowseMemory).toHaveBeenCalledTimes(1);
    expect(chrome.onBrowseTools).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("ignores profile browse shortcuts without an active profile", () => {
    const chrome = mountWindowChrome({ activeProfileName: null });

    press("S", { metaKey: true, shiftKey: true });

    expect(chrome.onBrowseSkills).not.toHaveBeenCalled();
    chrome.unmount();
  });

  it("opens notifications and shortcuts from any view", () => {
    const chrome = mountWindowChrome({ activeProfileName: null });

    press("o", { metaKey: true });
    press("/", { metaKey: true });

    expect(chrome.onToggleNotifications).toHaveBeenCalledTimes(1);
    expect(chrome.onToggleShortcuts).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("opens contextual history when available", () => {
    const chrome = mountWindowChrome({ historyKind: "tasks" });

    press("H", { metaKey: true, shiftKey: true });

    expect(chrome.onOpenHistory).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("ignores contextual history when no history target exists", () => {
    const chrome = mountWindowChrome({ historyKind: null });

    press("H", { metaKey: true, shiftKey: true });

    expect(chrome.onOpenHistory).not.toHaveBeenCalled();
    chrome.unmount();
  });
});
