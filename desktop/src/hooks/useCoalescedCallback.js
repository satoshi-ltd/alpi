import { useCallback, useEffect, useRef } from "react";

// Trailing debounce with a max-wait deadline — a continuous event stream keeps pushing the timer, the deadline stops it from starving the callback forever. Pending call dropped on unmount; last args win.
export function useCoalescedCallback(fn, delayMs, maxWaitMs = Infinity) {
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);
  const timerRef = useRef(null);
  const deadlineRef = useRef(0);
  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );
  return useCallback(
    (...args) => {
      const now = Date.now();
      if (!timerRef.current) deadlineRef.current = now + maxWaitMs;
      const fireIn = Math.min(delayMs, Math.max(0, deadlineRef.current - now));
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        fnRef.current?.(...args);
      }, fireIn);
    },
    [delayMs, maxWaitMs],
  );
}
