import { Animated } from 'react-native';

import { motion } from '../theme/tokens';

export const PULSE_HALF_MS = motion.pulse / 2;

export function pulseSteps(value, { from = 1, to = motion.pulseLow, useNativeDriver = true } = {}) {
  const step = (toValue) => Animated.timing(value, { toValue, duration: PULSE_HALF_MS, useNativeDriver });
  return [step(to), step(from)];
}
