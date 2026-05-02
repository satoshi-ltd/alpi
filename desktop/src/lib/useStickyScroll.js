import { useEffect, useRef } from "react";

const NEAR_BOTTOM_PX = 80;

export function useStickyScroll(deps) {
  const scrollRef = useRef(null);
  const stickRef = useRef(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return undefined;
    function onScroll() {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickRef.current = distance <= NEAR_BOTTOM_PX;
    }
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !stickRef.current) return;
    requestAnimationFrame(() => {
      if (el) el.scrollTop = el.scrollHeight;
    });
  }, deps);

  return scrollRef;
}
