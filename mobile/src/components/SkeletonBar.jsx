import { useEffect, useRef } from 'react';
import { Animated } from 'react-native';
import { radii } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';

export function SkeletonBar({ width, height = 12, style }) {
  const { colors } = useTheme();
  const op = useRef(new Animated.Value(0.4)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(op, { toValue: 0.8, duration: 700, useNativeDriver: true }),
        Animated.timing(op, { toValue: 0.4, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [op]);
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
