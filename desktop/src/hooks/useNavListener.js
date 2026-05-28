import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "../lib/tauri-listen.js";

export function useNavListener(setView) {
  useEffect(() => {
    let cancelled = false;
    let unlisten = null;
    listen("nav", (event) => {
      if (event.payload === "settings") {
        setView({ kind: "settings" });
      } else if (event.payload === "home") {
        setView((v) => (v.kind === "settings" ? { kind: "empty" } : v));
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
