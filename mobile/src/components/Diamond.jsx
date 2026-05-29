import { useEffect, useRef } from 'react';
import { Animated, Easing } from 'react-native';

import { glyphSize, glyphSizeMd, pulseDuration } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';

export function Diamond({ color, size, outlined = false, pulse = false }) {
  const { colors } = useTheme();
  const tint = color ?? colors.ink3;
  const dimension = size === 'md' ? glyphSizeMd : glyphSize;
  const opacity = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    if (!pulse) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.55, duration: pulseDuration / 2, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 1, duration: pulseDuration / 2, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, opacity]);
  return (
    <Animated.View
      style={{
        width: dimension,
        height: dimension,
        borderRadius: 2,
        transform: [{ rotate: '45deg' }],
        backgroundColor: outlined ? 'transparent' : tint,
        borderWidth: outlined ? 1.5 : 0,
        borderColor: outlined ? tint : 'transparent',
        opacity: pulse ? opacity : 1,
      }}
    />
  );
}
