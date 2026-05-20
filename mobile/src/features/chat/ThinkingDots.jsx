import { useEffect, useRef } from 'react';
import { Animated, View } from 'react-native';
import { space } from '../../theme/tokens';

import { useTheme } from '../../theme/ThemeContext';

function Dot({ delay, color }) {
  const op = useRef(new Animated.Value(0.3)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.delay(delay),
        Animated.timing(op, { toValue: 1, duration: 350, useNativeDriver: true }),
        Animated.timing(op, { toValue: 0.3, duration: 600, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [delay, op]);
  return (
    <Animated.View
      style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: color, opacity: op }}
    />
  );
}

export function ThinkingDots({ color }) {
  const { colors } = useTheme();
  const tint = color ?? colors.ink3;
  return (
    <View style={{ flexDirection: 'row', gap: space.s1, paddingHorizontal: space.s7 }}>
      <Dot delay={0} color={tint} />
      <Dot delay={150} color={tint} />
      <Dot delay={300} color={tint} />
    </View>
  );
}
