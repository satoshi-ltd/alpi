import { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { BUSY_LABEL, BUSY_WAVE_S } from '../../../common/busy.mjs';
import { useReduceMotion } from '../lib/reduceMotion';
import { useTheme } from '../theme/ThemeContext';

export const SPINNER_TURN_MS = (BUSY_WAVE_S * 1000) / 2;
export const SPINNER_SIZE = 20;

export function Spinner({ size = SPINNER_SIZE, color, label = BUSY_LABEL }) {
  const { colors } = useTheme();
  const reduceMotion = useReduceMotion();
  const turn = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (reduceMotion) return undefined;
    const loop = Animated.loop(Animated.timing(turn, { toValue: 1, duration: SPINNER_TURN_MS, easing: Easing.linear, useNativeDriver: true }));
    loop.start();
    return () => {
      loop.stop();
      turn.setValue(0);
    };
  }, [reduceMotion, turn]);
  const rotate = useMemo(() => (reduceMotion ? '0deg' : turn.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] })), [reduceMotion, turn]);
  return (
    <Animated.View
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      data-spinner=""
      style={{ width: size, height: size, transform: [{ rotate }] }}
    >
      <Svg width={size} height={size} viewBox="0 0 16 16" fill="none">
        <Path d="M8 2a6 6 0 1 0 6 6" stroke={color ?? colors.ink2} strokeWidth={1.5} strokeLinecap="round" />
      </Svg>
    </Animated.View>
  );
}
