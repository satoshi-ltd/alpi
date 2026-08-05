import { useEffect, useState } from "react";

export const TICK_MS = 30000;

const subscribers = new Set();
let timer = null;

function broadcast() {
  const now = Date.now();
  for (const notify of [...subscribers]) notify(now);
}

export function useNow() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    // One shared interval for every relative stamp — a per-stamp timer means hundreds of them in a long transcript.
    subscribers.add(setNow);
    if (!timer) timer = setInterval(broadcast, TICK_MS);
    return () => {
      subscribers.delete(setNow);
      if (subscribers.size === 0 && timer) {
        clearInterval(timer);
        timer = null;
      }
    };
  }, []);
  return now;
}
