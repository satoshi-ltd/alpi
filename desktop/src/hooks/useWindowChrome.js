import { useEffect } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";

export function useWindowChrome({
  viewRef,
  setView,
  onJumpToProfile,
  onNewProfile,
  onNewWorkgroup,
  onOpenSettings,
  onToggleSearch,
  onTogglePalette,
  paletteOpenRef,
  onClosePalette,
  activeProfileName = null,
  historyKind = null,
  onOpenHistory,
  onBrowseTools,
  onBrowseSkills,
  onBrowseMemory,
  onToggleNotifications,
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
    if (!viewRef || !setView) return;
    function onKey(e) {
      const cmd = e.metaKey || e.ctrlKey;
      if (!cmd) return;
      const key = e.key.toLowerCase();
      const isShortcut =
        /^[1-9]$/.test(key) ||
        key === "n" ||
        key === "," ||
        key === "f" ||
        key === "k" ||
        key === "o" ||
        key === "/" ||
        key === "?" ||
        (e.shiftKey && (key === "t" || key === "s" || key === "m" || key === "h" || key === "n" || key === "w"));
      if (paletteOpenRef?.current && isShortcut && key !== "k") {
        onClosePalette?.();
      }
      if (/^[1-9]$/.test(key)) {
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
        const kind = viewRef.current?.kind;
        if (kind === "profile") {
          e.preventDefault();
          e.stopPropagation();
          setView((v) => (v.kind === "profile" ? { ...v, sessionId: null } : v));
          return;
        }
        if (kind === "settings") {
          e.preventDefault();
          e.stopPropagation();
          onNewProfile?.();
          return;
        }
        if (kind === "empty" || kind === "workgroup") {
          e.preventDefault();
          e.stopPropagation();
          setView({ kind: "empty" });
          return;
        }
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
      if (key === "o" && !e.shiftKey && !e.altKey) {
        e.preventDefault();
        e.stopPropagation();
        onToggleNotifications?.();
        return;
      }
      if (key === "/" || key === "?") {
        e.preventDefault();
        e.stopPropagation();
        onToggleShortcuts?.();
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
      if (e.shiftKey && (key === "t" || key === "s" || key === "m")) {
        if (activeProfileName) {
          e.preventDefault();
          e.stopPropagation();
          if (key === "t") onBrowseTools?.();
          else if (key === "s") onBrowseSkills?.();
          else onBrowseMemory?.();
        }
      }
    }
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [viewRef, setView, onJumpToProfile, onNewProfile, onNewWorkgroup, onOpenSettings, onToggleSearch, onTogglePalette, paletteOpenRef, onClosePalette, activeProfileName, historyKind, onOpenHistory, onBrowseTools, onBrowseSkills, onBrowseMemory, onToggleNotifications, onToggleShortcuts]);
}
