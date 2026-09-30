import { useEffect, useRef } from 'react';
import { Animated, View } from 'react-native';
import { space } from '../../theme/tokens';

import { useReduceMotion } from '../../lib/reduceMotion';
import { useTheme } from '../../theme/ThemeContext';

function Dot({ delay, color, still }) {
  const op = useRef(new Animated.Value(still ? 0.6 : 0.3)).current;
  useEffect(() => {
    if (still) {
      op.setValue?.(0.6);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.delay(delay),
        Animated.timing(op, { toValue: 1, duration: 350, useNativeDriver: true }),
        Animated.timing(op, { toValue: 0.3, duration: 600, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [delay, op, still]);
  return (
    <Animated.View
      style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: color, opacity: op }}
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
