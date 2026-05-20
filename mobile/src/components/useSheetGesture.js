// `mounted` lags `open` by DURATION_OUT so the exit animation plays before <Modal> tears down.

import { useEffect, useState } from 'react';
import { Gesture } from 'react-native-gesture-handler';
import Animated, {
  Easing,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';

const EASE = Easing.bezier(0.2, 0.7, 0.2, 1);
const DURATION_IN = 220;
const DURATION_OUT = 200;
const UNMOUNT_BUFFER = 40; // small slack so the last frame of the timing animation still renders
const DISMISS_PX = 80;
const DISMISS_VELOCITY = 800;
const OFF_SCREEN = 900;

export function useSheetGesture(open, onClose) {
  const tx = useSharedValue(OFF_SCREEN);
  const backdrop = useSharedValue(0);
  // `mounted` keeps the Modal+children alive long enough for the exit animation to complete. It flips true synchronously when `open` becomes true (so the IN animation has a target to animate into) and false on a timer after `open` becomes false.
  const [mounted, setMounted] = useState(open);

  useEffect(() => {
    if (open) {
      setMounted(true);
      tx.value = withTiming(0, { duration: DURATION_IN, easing: EASE });
      backdrop.value = withTiming(1, { duration: DURATION_IN, easing: EASE });
      return undefined;
    }
    tx.value = withTiming(OFF_SCREEN, { duration: DURATION_OUT, easing: EASE });
    backdrop.value = withTiming(0, { duration: DURATION_OUT, easing: EASE });
    const t = setTimeout(() => setMounted(false), DURATION_OUT + UNMOUNT_BUFFER);
    return () => clearTimeout(t);
  }, [open, tx, backdrop]);

  const close = () => {
    onClose?.();
  };

  const gesture = Gesture.Pan()
    .activeOffsetY([8, 8])
    .onUpdate((e) => {
      if (e.translationY > 0) {
        tx.value = e.translationY;
      }
    })
    .onEnd((e) => {
      if (e.translationY > DISMISS_PX || e.velocityY > DISMISS_VELOCITY) {
        tx.value = withTiming(OFF_SCREEN, { duration: DURATION_OUT, easing: EASE }, () => runOnJS(close)());
        backdrop.value = withTiming(0, { duration: DURATION_OUT, easing: EASE });
      } else {
        tx.value = withTiming(0, { duration: DURATION_IN, easing: EASE });
      }
    });

  const sheetStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: tx.value }],
  }));

  const backdropStyle = useAnimatedStyle(() => ({
    opacity: backdrop.value,
  }));

  return { gesture, sheetStyle, backdropStyle, mounted, Animated };
}
