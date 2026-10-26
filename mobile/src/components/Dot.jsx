import { useEffect, useRef } from 'react';
import { Animated } from 'react-native';

import { useReduceMotion } from '../lib/reduceMotion';
import { pulseSteps } from '../lib/pulse';
import { useTheme } from '../theme/ThemeContext';
import { dotShape } from './dotShape';

export function Dot({ color, size = 'sm', pulse = false }) {
  const { colors } = useTheme();
  const opacity = useRef(new Animated.Value(1)).current;
  const reduceMotion = useReduceMotion();
  const pulsing = pulse && !reduceMotion;
  useEffect(() => {
    if (!pulsing) return;
    const loop = Animated.loop(Animated.sequence(pulseSteps(opacity)));
    loop.start();
    return () => loop.stop();
  }, [pulsing, opacity]);
  return (
    <Animated.View
      style={{
        ...dotShape(size),
        backgroundColor: color ?? colors.ink3,
        opacity: pulsing ? opacity : 1,
      }}
    />
  );
}
