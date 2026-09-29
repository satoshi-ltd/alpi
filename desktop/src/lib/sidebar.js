import { createContext, useCallback, useContext, useState } from "react";

const KEY = "alpi.sidebarOpen";

export const SidebarContext = createContext({ open: true, toggle: () => {} });

export function readSidebarPref() {
  try {
    const value = localStorage.getItem(KEY);
    return value == null ? true : value !== "0";
  } catch {
    return true;
  }
}

function writeSidebarPref(open) {
  try {
    localStorage.setItem(KEY, open ? "1" : "0");
  } catch {
    return;
  }
}

export function useSidebarPref() {
  const [open, setOpen] = useState(readSidebarPref);
  const toggle = useCallback(() => {
    setOpen((current) => {
      const next = !current;
      writeSidebarPref(next);
      return next;
    });
  }, []);
  return { open, toggle };
}

export function useSidebar() {
  return useContext(SidebarContext);
}
