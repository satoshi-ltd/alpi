import { useEffect, useLayoutEffect, useRef, useState } from 'react';

export function useSkeleton(loading, { delay = 150, minShown = 400 } = {}) {
  const [show, setShow] = useState(false);
  const shownAt = useRef(0);
  const loadingNow = useRef(loading);
  useLayoutEffect(() => {
    loadingNow.current = loading;
  }, [loading]);
  useEffect(() => {
    if (loading && !show) {
      const timer = setTimeout(() => {
        if (!loadingNow.current) return;
        shownAt.current = Date.now();
        setShow(true);
      }, delay);
      return () => clearTimeout(timer);
    }
    if (!loading && show) {
      const wait = Math.max(0, minShown - (Date.now() - shownAt.current));
      const timer = setTimeout(() => setShow(false), wait);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [loading, show, delay, minShown]);
  return show;
}
