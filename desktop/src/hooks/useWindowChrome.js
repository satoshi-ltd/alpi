import { useEffect } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";

export function useWindowChrome({
  viewRef,
  onNewSession = null,
  onJumpToProfile,
  onNewProfile,
  onNewWorkgroup,
  onOpenSettings,
  onToggleSearch,
  onToggleSidebarSearch,
  sidebarSearchAvailableRef,
  onTogglePalette,
  paletteOpenRef,
  onClosePalette,
  activeProfileName = null,
  historyKind = null,
  onOpenHistory,
  onRefreshThread,
  onToggleContextPause,
  onToggleReadAloud,
  onBrowseTools,
  onBrowseSkills,
  onBrowseMemory,
  onBrowseSchedule,
  onToggleNotifications,
  onToggleActivity,
  onToggleShortcuts,
} = {}) {
  useEffect(() => {
    function onDown(e) {
      if (e.button !== 0) return;
      const t = e.target;
      if (!(t instanceof Element)) return;
      if (
        t.closest(
          "button, input, textarea, select, a, [contenteditable], [data-no-drag]",
        )
      ) {
        return;
      }
      if (!t.closest("[data-drag]")) return;
      e.preventDefault();
      const win = getCurrentWindow();
      if (e.detail === 2) {
        win.toggleMaximize().catch(() => {});
      } else {
        win.startDragging().catch(() => {});
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  useEffect(() => {
    if (!viewRef) return;
    function onKey(e) {
      const cmd = e.metaKey || e.ctrlKey;
      if (!cmd) return;
      const key = e.key.toLowerCase();
      const canSidebarSearch = !!sidebarSearchAvailableRef?.current;
      const isSlash = key === "/" || e.code === "Slash";
      const isJump = /^[1-9]$/.test(key) && !e.shiftKey && !isSlash;
      const isShortcut =
        isJump ||
        key === "n" ||
        key === "," ||
        key === "f" ||
        key === "k" ||
        key === "o" ||
        (key === "j" && !!onToggleActivity) ||
        (isSlash && !!onToggleShortcuts) ||
        (key === "s" && !e.shiftKey && canSidebarSearch) ||
        (e.shiftKey && (key === "t" || key === "s" || key === "m" || key === "e" || key === "h" || key === "l" || key === "p" || key === "r" || key === "n" || key === "w"));
      if (paletteOpenRef?.current && isShortcut && key !== "k") {
        onClosePalette?.();
      }
      if (isSlash && !e.altKey) {
        if (onToggleShortcuts) {
          e.preventDefault();
          e.stopPropagation();
          onToggleShortcuts();
        }
        return;
      }
      if (isJump) {
        e.preventDefault();
        e.stopPropagation();
        onJumpToProfile?.(Number(key) - 1);
        return;
      }
      if (e.shiftKey && key === "n") {
        e.preventDefault();
        e.stopPropagation();
        onNewProfile?.();
        return;
      }
      if (e.shiftKey && key === "w") {
        e.preventDefault();
        e.stopPropagation();
        onNewWorkgroup?.();
        return;
      }
      if (key === "n") {
        if (!onNewSession) return;
        e.preventDefault();
        e.stopPropagation();
        onNewSession();
        return;
      }
      if (key === ",") {
        e.preventDefault();
        e.stopPropagation();
        // No fallback: member devices pass null intentionally to disable the shortcut.
        if (onOpenSettings) onOpenSettings();
        return;
      }
      if (key === "f") {
        const kind = viewRef.current?.kind;
        if (kind === "profile" || kind === "workgroup") {
          e.preventDefault();
          e.stopPropagation();
          onToggleSearch?.();
        }
        return;
      }
      if (key === "k") {
        e.preventDefault();
        e.stopPropagation();
        onTogglePalette?.();
        return;
      }
      if (key === "j" && !e.shiftKey && !e.altKey) {
        if (onToggleActivity) {
          e.preventDefault();
          e.stopPropagation();
          onToggleActivity();
        }
        return;
      }
      if (key === "o" && !e.shiftKey && !e.altKey) {
        e.preventDefault();
        e.stopPropagation();
        onToggleNotifications?.();
        return;
      }
      if (key === "s" && !e.shiftKey && !e.altKey && canSidebarSearch) {
        e.preventDefault();
        e.stopPropagation();
        onToggleSidebarSearch?.();
        return;
      }
      if (e.shiftKey && key === "l") {
        if (onToggleReadAloud) {
          e.preventDefault();
          e.stopPropagation();
          onToggleReadAloud();
        }
        return;
      }
      if (e.shiftKey && key === "r") {
        if (onRefreshThread) {
          e.preventDefault();
          e.stopPropagation();
          onRefreshThread();
        }
        return;
      }
      if (e.shiftKey && key === "p") {
        if (onToggleContextPause) {
          e.preventDefault();
          e.stopPropagation();
          onToggleContextPause();
        }
        return;
      }
      if (e.shiftKey && key === "h") {
        if (historyKind) {
          e.preventDefault();
          e.stopPropagation();
          onOpenHistory?.();
        }
        return;
      }
      if (e.shiftKey && (key === "t" || key === "s" || key === "m" || key === "e")) {
        if (activeProfileName) {
          e.preventDefault();
          e.stopPropagation();
          if (key === "t") onBrowseTools?.();
          else if (key === "s") onBrowseSkills?.();
          else if (key === "m") onBrowseMemory?.();
          else onBrowseSchedule?.();
        }
      }
    }
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [viewRef, onNewSession, onJumpToProfile, onNewProfile, onNewWorkgroup, onOpenSettings, onToggleSearch, onToggleSidebarSearch, sidebarSearchAvailableRef, onTogglePalette, paletteOpenRef, onClosePalette, activeProfileName, historyKind, onOpenHistory, onRefreshThread, onToggleContextPause, onToggleReadAloud, onBrowseTools, onBrowseSkills, onBrowseMemory, onBrowseSchedule, onToggleNotifications, onToggleActivity, onToggleShortcuts]);
}
