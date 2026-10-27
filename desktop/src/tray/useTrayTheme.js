import { useEffect } from "react";
import { THEME_KEY, applyStored } from "../lib/theme.js";

export function useTrayTheme() {
  useEffect(() => {
    applyStored();
    const onStorage = (event) => {
      if (event.key === null || event.key === THEME_KEY) applyStored();
    };
    const onVisible = () => {
      if (document.visibilityState !== "hidden") applyStored();
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener("focus", applyStored);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("focus", applyStored);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);
}
