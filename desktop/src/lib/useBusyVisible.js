import { useEffect, useRef, useState } from "react";
import { busyPlan } from "../../../common/busy.mjs";

export function useBusyVisible(active, resetKey = null) {
  const [shown, setShown] = useState({ visible: false, key: resetKey });
  const [wake, setWake] = useState(0);
  const startedAt = useRef(null);
  const shownAt = useRef(null);
  const lastKey = useRef(resetKey);

  useEffect(() => {
    const now = Date.now();
    if (lastKey.current !== resetKey) {
      lastKey.current = resetKey;
      startedAt.current = null;
      shownAt.current = null;
    }
    if (!active) startedAt.current = null;
    else if (startedAt.current == null) startedAt.current = now;
    const plan = busyPlan({ active, startedAt: startedAt.current, shownAt: shownAt.current }, now);
    if (!plan.visible) shownAt.current = null;
    else if (shownAt.current == null) shownAt.current = now;
    setShown({ visible: plan.visible, key: resetKey });
    if (plan.wakeIn == null) return undefined;
    const timer = setTimeout(() => setWake((n) => n + 1), plan.wakeIn);
    return () => clearTimeout(timer);
  }, [active, wake, resetKey]);

  return shown.visible && shown.key === resetKey;
}

const REDUCED = "(prefers-reduced-motion: reduce)";

export function useReducedMotion() {
  const query = () => (typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia(REDUCED) : null);
  const [reduced, setReduced] = useState(() => !!query()?.matches);
  useEffect(() => {
    const media = query();
    if (!media) return undefined;
    const onChange = () => setReduced(!!media.matches);
    onChange();
    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    }
    media.addListener?.(onChange);
    return () => media.removeListener?.(onChange);
  }, []);
  return reduced;
}
