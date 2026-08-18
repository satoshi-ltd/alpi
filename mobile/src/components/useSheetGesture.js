import { useEffect, useState } from 'react';
import { Gesture } from 'react-native-gesture-handler';
import Animated, {
  Easing,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';

export const EASE_IN = Easing.bezier(0.2, 0.7, 0.2, 1);
// Time-reverse of EASE_IN. Reusing EASE_IN for the exit covered 70% of a viewport-tall travel in the first 16ms, so the sheet was gone in one frame.
export const EASE_OUT = Easing.bezier(0.8, 0, 0.8, 0.3);
export const DURATION_IN = 220;
export const DURATION_OUT = 220;
export const UNMOUNT_BUFFER = 40;
const DISMISS_PX = 80;
const DISMISS_VELOCITY = 800;
const OFF_SCREEN = 900;

export function useSheetGesture(open, onClose, offScreen = OFF_SCREEN) {
  const tx = useSharedValue(offScreen);
  const backdrop = useSharedValue(0);
  const [mounted, setMounted] = useState(open);

  useEffect(() => {
    if (open) {
      setMounted(true);
      tx.value = withTiming(0, { duration: DURATION_IN, easing: EASE_IN });
      backdrop.value = withTiming(1, { duration: DURATION_IN, easing: EASE_IN });
      return undefined;
    }
    tx.value = withTiming(offScreen, { duration: DURATION_OUT, easing: EASE_OUT });
    backdrop.value = withTiming(0, { duration: DURATION_OUT, easing: EASE_OUT });
    const t = setTimeout(() => setMounted(false), DURATION_OUT + UNMOUNT_BUFFER);
    return () => clearTimeout(t);
  }, [open, offScreen, tx, backdrop]);

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
        tx.value = withTiming(offScreen, { duration: DURATION_OUT, easing: EASE_OUT }, () => runOnJS(close)());
        backdrop.value = withTiming(0, { duration: DURATION_OUT, easing: EASE_OUT });
      } else {
        tx.value = withTiming(0, { duration: DURATION_IN, easing: EASE_IN });
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
