import { useEffect, useState } from "react";

export function useDelayedFlag(active, delayMs = 450) {
  const [on, setOn] = useState(false);
  useEffect(() => {
    if (!active) {
      setOn(false);
      return undefined;
    }
    const t = setTimeout(() => setOn(true), delayMs);
    return () => clearTimeout(t);
  }, [active, delayMs]);
  return on;
}
