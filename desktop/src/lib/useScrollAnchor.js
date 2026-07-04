import { useLayoutEffect, useRef } from "react";

const NEAR_BOTTOM_PX = 80;

// Compensates scrollTop when turns are prepended above the viewport; bottom-stuck users are useStickyScroll's job, so they are skipped here.
export function useScrollAnchor(scrollRef, firstIndex, resetKey = null) {
  const stateRef = useRef({ el: null, firstIndex, resetKey, scrollHeight: 0, scrollTop: 0, onScroll: null });

  useLayoutEffect(() => {
    const s = stateRef.current;
    const el = scrollRef?.current ?? null;
    const keyChanged = s.resetKey !== resetKey;
    s.resetKey = resetKey;
    if (s.el !== el) {
      if (s.el && s.onScroll) s.el.removeEventListener("scroll", s.onScroll);
      s.onScroll = null;
      s.el = el;
      if (el) {
        s.onScroll = () => {
          s.scrollTop = el.scrollTop;
          s.scrollHeight = el.scrollHeight;
        };
        el.addEventListener("scroll", s.onScroll, { passive: true });
      }
    } else if (el && !keyChanged && firstIndex < s.firstIndex) {
      const delta = el.scrollHeight - s.scrollHeight;
      const distance = s.scrollHeight - s.scrollTop - el.clientHeight;
      if (delta > 0 && distance > NEAR_BOTTOM_PX) {
        el.scrollTop = s.scrollTop + delta;
      }
    }
    s.firstIndex = firstIndex;
    s.scrollHeight = el?.scrollHeight ?? 0;
    s.scrollTop = el?.scrollTop ?? 0;
  });

  useLayoutEffect(
    () => () => {
      const s = stateRef.current;
      if (s.el && s.onScroll) s.el.removeEventListener("scroll", s.onScroll);
    },
    [],
  );
}
