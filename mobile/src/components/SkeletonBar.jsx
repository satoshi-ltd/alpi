import { useEffect, useRef } from 'react';
import { Animated } from 'react-native';
import { radii } from '../theme/tokens';

import { useReduceMotion } from '../lib/reduceMotion';
import { useTheme } from '../theme/ThemeContext';

export function SkeletonBar({ width, height = 12, delay = 0, style }) {
  const { colors } = useTheme();
  const reduceMotion = useReduceMotion();
  const op = useRef(new Animated.Value(0.4)).current;
  useEffect(() => {
    if (reduceMotion) {
      op.setValue(0.6);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(op, { toValue: 0.8, duration: 700, useNativeDriver: true }),
        Animated.timing(op, { toValue: 0.4, duration: 700, useNativeDriver: true }),
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
          borderRadius: radii.xs,
          backgroundColor: colors.hover,
          opacity: op,
        },
        style,
      ]}
    />
  );
}
