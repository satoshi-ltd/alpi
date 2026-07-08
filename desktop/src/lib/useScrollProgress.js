import { useCallback, useEffect, useRef, useState } from "react";

const DEFAULT_THRESHOLD = 200;

export function useScrollProgress(
  scrollRef,
  { threshold = DEFAULT_THRESHOLD } = {},
) {
  const [farFromBottom, setFarFromBottom] = useState(false);
  const rafRef = useRef(0);

  const measure = useCallback(() => {
    const el = scrollRef?.current;
    if (!el) {
      setFarFromBottom(false);
      return;
    }
    const overflow = el.scrollHeight - el.clientHeight;
    if (overflow <= threshold) {
      // Content fits in (or barely overflows) one viewport — never useful.
      setFarFromBottom(false);
      return;
    }
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    setFarFromBottom(distance > threshold);
  }, [scrollRef, threshold]);

  // Re-attach when the ref's target appears or changes (e.g. after a loading
  // → transcript transition). Poll until we see a non-null el, then bind.
  useEffect(() => {
    let bound = null;
    let interval = 0;

    function onScroll() {
      if (rafRef.current) return;
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = 0;
        measure();
      });
    }

    function bind(el) {
      if (bound === el) return;
      unbind();
      bound = el;
      el.addEventListener("scroll", onScroll, { passive: true });
      measure();
      const ro = new ResizeObserver(() => measure());
      ro.observe(el);
      if (el.firstElementChild) ro.observe(el.firstElementChild);
      bound.__roP = ro;
    }

    function unbind() {
      if (!bound) return;
      bound.removeEventListener("scroll", onScroll);
      bound.__roP?.disconnect();
      bound.__roP = null;
      bound = null;
    }

    function tick() {
      const el = scrollRef?.current;
      if (el && el !== bound) bind(el);
      else if (!el && bound) unbind();
    }

    tick();
    interval = setInterval(tick, 250);

    return () => {
      clearInterval(interval);
      unbind();
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [scrollRef, measure]);

  const scrollToBottom = useCallback(() => {
    const el = scrollRef?.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [scrollRef]);

  return {
    farFromBottom,
    scrollToBottom,
  };
}
