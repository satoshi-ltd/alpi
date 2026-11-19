import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "../lib/tauri-listen.js";
import { LANDING_VIEW } from "../lib/landing.js";
import { modalLayerOpen } from "./useOverlay.js";

export function useNavListener(setView, toggleSettingsRef = null, openSettingsRef = null) {
  useEffect(() => {
    let cancelled = false;
    let unlisten = null;
    listen("nav", (event) => {
      if (event.payload === "settings" || event.payload === "settings-toggle" || event.payload === "settings-open") {
        // The native menu's ⌘, arrives here as settings-toggle (window in front) or settings-open (window brought back), not through the window shortcuts, so a dialog must gate it too; the tray's settings only opens.
        if (modalLayerOpen()) return;
        if (event.payload === "settings-toggle" && toggleSettingsRef?.current) toggleSettingsRef.current();
        else if (event.payload === "settings-open" && openSettingsRef?.current) openSettingsRef.current();
        else setView({ kind: "settings" });
      } else if (event.payload === "home") {
        setView((v) => (v.kind === "settings" ? LANDING_VIEW : v));
      }
    })
      .then((fn) => {
        if (cancelled) safeUnlisten(fn);
        else unlisten = fn;
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      safeUnlisten(unlisten);
    };
  }, [setView]);
}
