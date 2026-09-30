import { useCallback, useEffect, useRef, useState } from 'react';
import { Easing, cancelAnimation, useSharedValue, withTiming } from 'react-native-reanimated';
import { scheduleOnRN } from 'react-native-worklets';

import { useReduceMotion } from './reduceMotion';

export const PRESENCE_EASE = Easing.bezier(0.2, 0, 0, 1);

export function usePresence(visible, duration, { snap = false } = {}) {
  const reduceMotion = useReduceMotion();
  const [mounted, setMounted] = useState(visible);
  const progress = useSharedValue(visible ? 1 : 0);
  const moving = useSharedValue(false);
  const gen = useRef(0);
  const first = useRef(true);
  const snapRef = useRef(snap);
  snapRef.current = snap;
  const settle = useCallback((g) => {
    if (g === gen.current) setMounted(false);
  }, []);
  useEffect(() => {
    gen.current += 1;
    const g = gen.current;
    const target = visible ? 1 : 0;
    const initial = first.current;
    first.current = false;
    if (visible) setMounted(true);
    if (initial || reduceMotion || snapRef.current) {
      cancelAnimation(progress);
      progress.value = target;
      moving.value = false;
      if (!visible) setMounted(false);
      return;
    }
    if (progress.value === target && !moving.value) {
      if (!visible) setMounted(false);
      return;
    }
    moving.value = true;
    progress.value = withTiming(target, { duration, easing: PRESENCE_EASE }, (finished) => {
      if (!finished) return;
      moving.value = false;
      if (!visible) scheduleOnRN(settle, g);
    });
  }, [visible, reduceMotion, duration, progress, moving, settle]);
  return { mounted: mounted || visible, progress, moving, reduceMotion };
}
