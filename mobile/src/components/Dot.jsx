import { useEffect, useRef } from 'react';
import { Animated, Easing } from 'react-native';

import { dotSize, pulseDuration } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';

export function Dot({ color, pulse = false }) {
  const { colors } = useTheme();
  const opacity = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    if (!pulse) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.4, duration: pulseDuration / 2, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 1, duration: pulseDuration / 2, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, opacity]);
  return (
    <Animated.View
      style={{
        width: dotSize,
        height: dotSize,
        borderRadius: dotSize / 2,
        backgroundColor: color ?? colors.ink3,
        opacity: pulse ? opacity : 1,
      }}
    />
  );
}
