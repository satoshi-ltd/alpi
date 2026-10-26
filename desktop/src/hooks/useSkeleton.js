import { useEffect, useRef, useState } from "react";

export function useSkeletonPhase(loading, { delay = 150, minShown = 400 } = {}) {
  const [show, setShow] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const shownAt = useRef(0);

  useEffect(() => {
    if (loading) {
      if (show) return undefined;
      const id = setTimeout(() => {
        shownAt.current = Date.now();
        setShow(true);
        setRevealed(true);
      }, delay);
      return () => clearTimeout(id);
    }
    if (!show) return undefined;
    const wait = Math.max(0, minShown - (Date.now() - shownAt.current));
    const id = setTimeout(() => setShow(false), wait);
    return () => clearTimeout(id);
  }, [loading, show, delay, minShown]);

  return { show, revealed };
}

export function useSkeleton(loading, options) {
  return useSkeletonPhase(loading, options).show;
}
