import { useEffect, useRef } from 'react';
import { ActivityIndicator, Animated, Text, View } from 'react-native';
import { radii, space , fontSizes} from '../../theme/tokens';

import { Diamond } from '../../components/Diamond';
import { useTheme } from '../../theme/ThemeContext';

function mixHex(hex, pct, base) {
  const fromHex = (h) => {
    const v = h.replace('#', '');
    return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
  };
  const [r1, g1, b1] = fromHex(hex);
  const [r2, g2, b2] = fromHex(base);
  const r = Math.round(r1 * pct + r2 * (1 - pct));
  const g = Math.round(g1 * pct + g2 * (1 - pct));
  const b = Math.round(b1 * pct + b2 * (1 - pct));
  return `rgb(${r},${g},${b})`;
}

function formatArgs(value) {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map(formatArgs).join(' ');
  if (typeof value === 'object') {
    return Object.entries(value)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`)
      .join(' ');
  }
  return String(value);
}

export function ToolCallRow({ name, status = 'success', args, accent }) {
  const { colors, fonts , fontSizes} = useTheme();
  const isRunning = status === 'running';
  const isError = status === 'error';

  const baseBg = mixHex(colors.ink, 0.03, colors.bgPane);
  const runningBg = accent ? mixHex(accent, 0.05, colors.bgPane) : baseBg;
  const runningBorder = accent ? mixHex(accent, 0.55, colors.bgPane) : colors.line;

  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (!isRunning) return undefined;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: false }),
        Animated.timing(pulse, { toValue: 0, duration: 700, useNativeDriver: false }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [isRunning, pulse]);
  const shadowOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0, 0.35] });

  const diamondColor = isError ? colors.danger : (accent ?? colors.ink3);
  const argsStr = formatArgs(args);

  return (
    <View style={{ paddingHorizontal: space.s7 }}>
      <Animated.View
        style={{
          alignSelf: 'flex-start',
          flexDirection: 'row',
          alignItems: 'center',
          gap: space.s3,
          paddingHorizontal: space.s5,
          paddingVertical: space.s2,
          borderRadius: radii.sm,
          backgroundColor: isRunning ? runningBg : baseBg,
          borderWidth: 0.5,
          borderColor: isRunning ? runningBorder : (isError ? mixHex(colors.danger, 0.4, colors.bgPane) : colors.line),
          maxWidth: '100%',
          shadowColor: accent ?? colors.ink,
          shadowOpacity: isRunning ? shadowOpacity : 0,
          shadowRadius: 6,
          shadowOffset: { width: 0, height: 0 },
        }}
      >
        <Diamond color={diamondColor} size={7} />
        <Text
          style={{
            fontFamily: fonts.monoMedium,
            fontSize: fontSizes.sm,
            lineHeight: 14,
            color: colors.ink,
            includeFontPadding: false,
          }}
        >
          {name}
        </Text>
        {argsStr ? (
          <Text
            numberOfLines={1}
            style={{
              flex: 1,
              minWidth: 0,
              fontFamily: fonts.mono,
              fontSize: fontSizes.sm,
              lineHeight: 14,
              color: colors.ink3,
              includeFontPadding: false,
            }}
          >
            {argsStr}
          </Text>
        ) : null}
        {isRunning ? (
          <ActivityIndicator size="small" color={accent ?? colors.ink3} style={{ marginLeft: space.s1, transform: [{ scale: 0.7 }] }} />
        ) : null}
      </Animated.View>
    </View>
  );
}
