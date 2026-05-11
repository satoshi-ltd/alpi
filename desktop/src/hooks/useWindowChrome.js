import { useCallback, useEffect, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";

const COLLAPSE_BELOW = 600;
const EXPAND_ABOVE = 720;

export function useWindowChrome({
  viewRef,
  setView,
  onJumpToProfile,
  onNewProfile,
  onOpenSettings,
  onToggleSearch,
  onTogglePalette,
  paletteOpenRef,
  onClosePalette,
} = {}) {
  const [collapsed, setCollapsed] = useState(false);
  const toggleSidebar = useCallback(() => setCollapsed((c) => !c), []);

  // Drag-to-move on `[data-drag]` regions; double-click toggles maximize.
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

  // Auto-collapse the sidebar at narrow widths; expand above the threshold.
  useEffect(() => {
    function onResize() {
      const w = window.innerWidth;
      if (w < COLLAPSE_BELOW) setCollapsed(true);
      else if (w > EXPAND_ABOVE) setCollapsed(false);
    }
    window.addEventListener("resize", onResize);
    onResize();
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // ⌘B sidebar, ⌘N new session, ⌘, settings.
  useEffect(() => {
    if (!viewRef || !setView) return;
    function onKey(e) {
      const cmd = e.metaKey || e.ctrlKey;
      if (!cmd) return;
      const key = e.key.toLowerCase();
      const isShortcut =
        /^[1-9]$/.test(key) ||
        key === "b" ||
        key === "n" ||
        key === "," ||
        key === "f" ||
        key === "k";
      if (paletteOpenRef?.current && isShortcut && key !== "k") {
        onClosePalette?.();
      }
      if (/^[1-9]$/.test(key)) {
        e.preventDefault();
        e.stopPropagation();
        onJumpToProfile?.(Number(key) - 1);
        return;
      }
      if (key === "b") {
        if (viewRef.current?.kind === "settings") return;
        e.preventDefault();
        e.stopPropagation();
        setCollapsed((c) => !c);
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
        if (onOpenSettings) onOpenSettings();
        else setView({ kind: "settings" });
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
      }
    }
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [viewRef, setView, onJumpToProfile, onNewProfile, onOpenSettings, onToggleSearch, onTogglePalette, paletteOpenRef, onClosePalette]);

  return { collapsed, setCollapsed, toggleSidebar };
}
