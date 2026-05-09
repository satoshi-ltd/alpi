import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";

export function useNavListener(setView) {
  useEffect(() => {
    const off = listen("nav", (event) => {
      if (event.payload === "settings") {
        setView({ kind: "settings" });
      } else if (event.payload === "home") {
        setView((v) => (v.kind === "settings" ? { kind: "empty" } : v));
      }
    });
    return () => {
      off.then((fn) => fn());
    };
  }, [setView]);
}
