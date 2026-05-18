import { useEffect, useState } from "react";

const KEY = "alpi.theme";
const ORDER = ["light", "dark", "system"];

export function getTheme() {
  if (typeof localStorage === "undefined") return "system";
  const v = localStorage.getItem(KEY);
  return ORDER.includes(v) ? v : "system";
}

function apply(theme) {
  if (typeof document === "undefined") return;
  const html = document.documentElement;
  if (theme === "system") html.removeAttribute("data-mode");
  else html.setAttribute("data-mode", theme);
}

export function setTheme(theme) {
  if (!ORDER.includes(theme)) theme = "system";
  if (typeof localStorage !== "undefined") localStorage.setItem(KEY, theme);
  apply(theme);
  window.dispatchEvent(new CustomEvent("alpi-theme", { detail: { theme } }));
}

export function cycleTheme(current = getTheme()) {
  const i = ORDER.indexOf(current);
  const next = ORDER[(i + 1) % ORDER.length];
  setTheme(next);
  return next;
}

export function nextTheme(current = getTheme()) {
  const i = ORDER.indexOf(current);
  return ORDER[(i + 1) % ORDER.length];
}

export function applyStored() {
  apply(getTheme());
}

export function useTheme() {
  const [theme, set] = useState(getTheme);
  useEffect(() => {
    const onChange = (e) => set(e.detail?.theme ?? getTheme());
    window.addEventListener("alpi-theme", onChange);
    return () => window.removeEventListener("alpi-theme", onChange);
  }, []);
  return theme;
}
