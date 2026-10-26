import { useEffect, useRef } from 'react';
import { Animated } from 'react-native';
import { motion, radii } from '../theme/tokens';

import { pulseSteps } from '../lib/pulse';
import { useReduceMotion } from '../lib/reduceMotion';
import { useTheme } from '../theme/ThemeContext';

export const BREATH_LOW = motion.pulseLow;
export const STAGGER_MS = 90;

export function SkeletonBar({ width, height = 12, delay = 0, radius = radii.xs, style }) {
  const { colors } = useTheme();
  const reduceMotion = useReduceMotion();
  const op = useRef(new Animated.Value(reduceMotion ? 1 : BREATH_LOW)).current;
  useEffect(() => {
    if (reduceMotion) {
      op.setValue(1);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        ...pulseSteps(op, { from: BREATH_LOW, to: 1 }),
      ]),
    );
    const t = setTimeout(() => loop.start(), delay);
    return () => { clearTimeout(t); loop.stop(); };
  }, [op, delay, reduceMotion]);
  return (
    <Animated.View
      style={[
        {
          width,
          height,
          borderRadius: radius,
          backgroundColor: colors.line,
          opacity: op,
        },
        style,
      ]}
    />
  );
}
