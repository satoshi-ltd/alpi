import { useEffect, useReducer, useRef, useState } from 'react';

import { busyPlan } from '../../../common/busy.mjs';

export function useBusyVisible(active) {
  const [visible, setVisible] = useState(false);
  const [tick, wake] = useReducer((n) => n + 1, 0);
  const startedAt = useRef(null);
  const shownAt = useRef(null);
  useEffect(() => {
    const now = Date.now();
    if (!active) startedAt.current = null;
    else if (startedAt.current == null) startedAt.current = now;
    const plan = busyPlan({ active: !!active, startedAt: startedAt.current, shownAt: shownAt.current }, now);
    if (plan.visible && shownAt.current == null) shownAt.current = now;
    if (!plan.visible) shownAt.current = null;
    setVisible(plan.visible);
    if (plan.wakeIn == null) return undefined;
    const timer = setTimeout(wake, plan.wakeIn);
    return () => clearTimeout(timer);
  }, [active, tick]);
  return visible;
}
