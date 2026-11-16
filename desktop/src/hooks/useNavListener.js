import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "../lib/tauri-listen.js";
import { LANDING_VIEW } from "../lib/landing.js";
import { modalLayerOpen } from "./useOverlay.js";

export function useNavListener(setView, toggleSettingsRef = null) {
  useEffect(() => {
    let cancelled = false;
    let unlisten = null;
    listen("nav", (event) => {
      if (event.payload === "settings" || event.payload === "settings-toggle") {
        // The native menu's ⌘, arrives here as settings-toggle, not through the window shortcuts, so a dialog must gate it too; the tray's settings only opens.
        if (modalLayerOpen()) return;
        if (event.payload === "settings-toggle" && toggleSettingsRef?.current) toggleSettingsRef.current();
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
