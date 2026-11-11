import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "../lib/tauri-listen.js";
import { LANDING_VIEW } from "../lib/landing.js";
import { modalLayerOpen } from "./useOverlay.js";

export function useNavListener(setView) {
  useEffect(() => {
    let cancelled = false;
    let unlisten = null;
    listen("nav", (event) => {
      if (event.payload === "settings") {
        // The native menu's ⌘, arrives here, not through the window shortcuts, so a dialog must gate it too.
        if (!modalLayerOpen()) setView({ kind: "settings" });
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
