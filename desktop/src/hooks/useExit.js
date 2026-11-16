import { useEffect, useState } from "react";

const EXIT_FALLBACK_MS = 140;

function instant() {
  return typeof window === "undefined" || typeof window.matchMedia !== "function" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function useExit(open) {
  const [kept, setKept] = useState(open);
  if (open && !kept) setKept(true);

  useEffect(() => {
    if (open || !kept) return undefined;
    if (instant()) {
      setKept(false);
      return undefined;
    }
    const timer = setTimeout(() => setKept(false), EXIT_FALLBACK_MS);
    return () => clearTimeout(timer);
  }, [open, kept]);

  const mounted = open || (kept && !instant());
  return { mounted, closing: mounted && !open };
}
