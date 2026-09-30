import { useEffect, useRef } from 'react';
import { Animated, Text, View } from 'react-native';

import { useReduceMotion } from '../../lib/reduceMotion';
import { lineHeights, pulseDuration, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';

const DOT = 6;

export const STATE_TEXT = { 'needs-you': 'needs you', failed: 'failed', working: 'working' };

export function stateColor(state, colors) {
  if (state === 'needs-you') return colors.warningText ?? colors.warning;
  if (state === 'failed') return colors.dangerText ?? colors.danger;
  return colors.accent;
}

function PulseDot({ color, pulse }) {
  const opacity = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    if (!pulse) {
      opacity.setValue(1);
      return undefined;
    }
    const half = pulseDuration / 2;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.3, duration: half, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 1, duration: half, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, opacity]);
  return (
    <Animated.View
      testID={pulse ? 'state-pulse' : 'state-dot'}
      style={{ width: DOT, height: DOT, borderRadius: DOT / 2, backgroundColor: color, opacity }}
    />
  );
}

export function RowState({ state, phases }) {
  const { colors, fonts, fontSizes } = useTheme();
  const reduceMotion = useReduceMotion();
  if (!state) return null;
  const color = stateColor(state, colors);
  const text = phases ?? STATE_TEXT[state];
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
      <PulseDot color={color} pulse={state === 'working' && !reduceMotion} />
      <Text
        numberOfLines={1}
        style={{
          fontFamily: phases ? fonts.monoMedium : fonts.sans.medium,
          fontSize: fontSizes.xs,
          lineHeight: fontSizes.xs * lineHeights.cozy,
          color,
        }}
      >
        {text}
      </Text>
    </View>
  );
}
