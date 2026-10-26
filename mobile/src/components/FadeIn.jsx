import { useEffect, useRef } from 'react';
import { Animated } from 'react-native';

import { useReduceMotion } from '../lib/reduceMotion';
import { motion } from '../theme/tokens';

export function FadeIn({ children, style, animate = true }) {
  const reduceMotion = useReduceMotion();
  const op = useRef(new Animated.Value(reduceMotion || !animate ? 1 : 0)).current;
  useEffect(() => {
    if (reduceMotion || !animate) {
      op.setValue(1);
      return undefined;
    }
    const fade = Animated.timing(op, { toValue: 1, duration: motion.enter, useNativeDriver: true });
    fade.start();
    return () => fade.stop();
  }, [op, reduceMotion, animate]);
  return <Animated.View style={[{ opacity: op }, style]}>{children}</Animated.View>;
}
