import { useEffect, useLayoutEffect, useRef, useState } from "react";

export function useSkeletonPhase(loading, { delay = 150, minShown = 400 } = {}) {
  const [show, setShow] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const shownAt = useRef(0);
  const loadingNow = useRef(loading);
  useLayoutEffect(() => {
    loadingNow.current = loading;
  }, [loading]);

  useEffect(() => {
    if (loading) {
      if (show) return undefined;
      const id = setTimeout(() => {
        // The render that ends loading commits before this effect's cleanup clears the timer.
        if (!loadingNow.current) return;
        shownAt.current = Date.now();
        setShow(true);
        setRevealed(true);
      }, delay);
      return () => clearTimeout(id);
    }
    if (!show) return undefined;
    const wait = Math.max(0, minShown - (Date.now() - shownAt.current));
    const id = setTimeout(() => {
      if (!loadingNow.current) setShow(false);
    }, wait);
    return () => clearTimeout(id);
  }, [loading, show, delay, minShown]);

  return { show, revealed };
}

export function useSkeleton(loading, options) {
  return useSkeletonPhase(loading, options).show;
}
