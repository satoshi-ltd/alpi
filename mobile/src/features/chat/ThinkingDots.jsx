import { useEffect, useRef } from 'react';
import { Animated, View } from 'react-native';
import { motion, space } from '../../theme/tokens';

import { dotShape } from '../../components/dotShape';
import { pulseSteps } from '../../lib/pulse';
import { useReduceMotion } from '../../lib/reduceMotion';
import { useTheme } from '../../theme/ThemeContext';

function Dot({ delay, color, still }) {
  const op = useRef(new Animated.Value(still ? 0.6 : motion.pulseLow)).current;
  useEffect(() => {
    if (still) {
      op.setValue?.(0.6);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.delay(delay),
        ...pulseSteps(op, { from: motion.pulseLow, to: 1 }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [delay, op, still]);
  return (
    <Animated.View
      style={{ ...dotShape('sm'), backgroundColor: color, opacity: op }}
    />
  );
}

export function ThinkingDots({ color, padded = true }) {
  const { colors } = useTheme();
  const tint = color ?? colors.ink3;
  const still = useReduceMotion();
  return (
    <View style={{ flexDirection: 'row', gap: space.s1, paddingHorizontal: padded ? space.s7 : 0 }}>
      <Dot delay={0} color={tint} still={still} />
      <Dot delay={150} color={tint} still={still} />
      <Dot delay={300} color={tint} still={still} />
    </View>
  );
}
