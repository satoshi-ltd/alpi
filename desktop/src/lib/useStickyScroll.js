import { useEffect, useRef } from "react";

const NEAR_BOTTOM_PX = 80;

// `stickKey` (optional): when it changes, follow re-engages even if the user had
// scrolled up — pass the in-flight turn id so sending a message snaps to the stream.
export function useStickyScroll(deps, stickKey) {
  const scrollRef = useRef(null);
  const stickRef = useRef(true);
  const keyRef = useRef(stickKey);
  const rafRef = useRef(0);

  if (stickKey !== keyRef.current) {
    keyRef.current = stickKey;
    stickRef.current = true;
  }

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
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      const cur = scrollRef.current;
      if (cur && stickRef.current) cur.scrollTop = cur.scrollHeight;
    });
  }, deps);

  useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); }, []);

  return scrollRef;
}
