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
    onNewSession: vi.fn(),
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

  it("toggles the sidebar filter on ⌘S without shift when available", () => {
    const onToggleSidebarSearch = vi.fn();
    const chrome = mountWindowChrome({
      onToggleSidebarSearch,
      sidebarSearchAvailableRef: { current: true },
    });

    press("s", { metaKey: true });

    expect(onToggleSidebarSearch).toHaveBeenCalledTimes(1);
    expect(chrome.onBrowseSkills).not.toHaveBeenCalled();
    chrome.unmount();
  });

  it("ignores ⌘S when the sidebar filter is unavailable", () => {
    const onToggleSidebarSearch = vi.fn();
    const chrome = mountWindowChrome({
      onToggleSidebarSearch,
      sidebarSearchAvailableRef: { current: false },
    });

    press("s", { metaKey: true });

    expect(onToggleSidebarSearch).not.toHaveBeenCalled();
    chrome.unmount();
  });

  it("keeps ⇧⌘S on skills, not the sidebar filter", () => {
    const onToggleSidebarSearch = vi.fn();
    const chrome = mountWindowChrome({ onToggleSidebarSearch });

    press("s", { metaKey: true, shiftKey: true });

    expect(onToggleSidebarSearch).not.toHaveBeenCalled();
    expect(chrome.onBrowseSkills).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("opens notifications from any view", () => {
    const chrome = mountWindowChrome({ activeProfileName: null });

    press("o", { metaKey: true });

    expect(chrome.onToggleNotifications).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("opens the shortcuts sheet on ⌘/ and nothing else", () => {
    const onToggleShortcuts = vi.fn();
    const chrome = mountWindowChrome({ activeProfileName: null, onToggleShortcuts });

    press("/", { metaKey: true });

    expect(onToggleShortcuts).toHaveBeenCalledTimes(1);
    expect(chrome.onToggleNotifications).not.toHaveBeenCalled();
    expect(chrome.onOpenHistory).not.toHaveBeenCalled();
    chrome.unmount();
  });

  it("toggles the activity panel on ⌘J and closes an open palette first", () => {
    const onToggleActivity = vi.fn();
    const onClosePalette = vi.fn();
    const chrome = mountWindowChrome({ onToggleActivity, onClosePalette, paletteOpenRef: { current: true } });

    press("j", { metaKey: true });

    expect(onToggleActivity).toHaveBeenCalledTimes(1);
    expect(onClosePalette).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });

  it("leaves ⌘J alone when the daemon has no activity verb", () => {
    const chrome = mountWindowChrome({ onToggleActivity: null });
    const ev = new KeyboardEvent("keydown", { key: "j", metaKey: true, cancelable: true });
    window.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBe(false);
    chrome.unmount();
  });

  it("starts a new session on ⌘N from Settings and keeps New profile on ⇧⌘N", () => {
    const onNewProfile = vi.fn();
    const settings = mountWindowChrome({ onNewProfile });
    press("n", { metaKey: true });
    expect(settings.onNewSession).toHaveBeenCalledTimes(1);
    expect(onNewProfile).not.toHaveBeenCalled();
    press("N", { metaKey: true, shiftKey: true });
    expect(onNewProfile).toHaveBeenCalledTimes(1);
    expect(settings.onNewSession).toHaveBeenCalledTimes(1);
    settings.unmount();
  });

  it("starts a new session on ⌘N from a profile, a workgroup, the workgroups list and the landing", () => {
    for (const kind of ["profile", "workgroup", "workgroups", "landing"]) {
      const chrome = mountWindowChrome({ viewRef: { current: { kind } } });
      press("n", { metaKey: true });
      expect(chrome.onNewSession).toHaveBeenCalledTimes(1);
      chrome.unmount();
    }
  });

  it("leaves ⌘N alone with no profiles to start a session with", () => {
    const chrome = mountWindowChrome({ viewRef: { current: { kind: "workgroup" } }, onNewSession: null });
    const ev = new KeyboardEvent("keydown", { key: "n", metaKey: true, cancelable: true });
    window.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBe(false);
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

describe("useWindowChrome on non-US layouts", () => {
  it("opens the shortcuts sheet for ⇧⌘7 producing '/' and never jumps to slot 7", () => {
    const onToggleShortcuts = vi.fn();
    const onJumpToProfile = vi.fn();
    const chrome = mountWindowChrome({ onToggleShortcuts, onJumpToProfile });
    press("/", { metaKey: true, shiftKey: true, code: "Digit7" });
    press("7", { metaKey: true, shiftKey: true, code: "Digit7" });
    expect(onToggleShortcuts).toHaveBeenCalledTimes(1);
    expect(onJumpToProfile).not.toHaveBeenCalled();
    press("7", { metaKey: true, code: "Digit7" });
    expect(onJumpToProfile).toHaveBeenCalledWith(6);
    chrome.unmount();
  });

  it("falls back to the physical Slash key when the layout reports another character", () => {
    const onToggleShortcuts = vi.fn();
    const chrome = mountWindowChrome({ onToggleShortcuts });
    press("-", { metaKey: true, code: "Slash" });
    expect(onToggleShortcuts).toHaveBeenCalledTimes(1);
    chrome.unmount();
  });
});
