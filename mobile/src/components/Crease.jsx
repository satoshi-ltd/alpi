import { useId, useMemo, useState } from 'react';
import { Text, View } from 'react-native';
import Svg, { Defs, LinearGradient, Stop, Text as SvgText } from 'react-native-svg';

import { CREASE_ANGLE, CREASE_SLIT, creaseTones } from '../../../common/crease.mjs';
import { fonts as tokenFonts } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { creaseWidth } from './creaseMetrics';

const FLOOR_SIZE = 24;
const PLAIN_SIZE = 18;
const LINE_HEIGHT = 1.25;
const BASELINE = 0.98;
const BANDS = [0.33, 0.66];

export function creaseStops(tones, length) {
  const slit = Math.min(CREASE_SLIT / length, 0.02);
  const [a, b, c] = tones;
  const [first, second] = BANDS;
  return [
    { offset: 0, color: a, opacity: 1 },
    { offset: first - slit, color: a, opacity: 1 },
    { offset: first - slit, color: a, opacity: 0 },
    { offset: first + slit, color: b, opacity: 0 },
    { offset: first + slit, color: b, opacity: 1 },
    { offset: second - slit, color: b, opacity: 1 },
    { offset: second - slit, color: b, opacity: 0 },
    { offset: second + slit, color: c, opacity: 0 },
    { offset: second + slit, color: c, opacity: 1 },
    { offset: 1, color: c, opacity: 1 },
  ];
}

export function creaseAxis(width, height) {
  const rad = (CREASE_ANGLE * Math.PI) / 180;
  const dx = Math.sin(rad);
  const dy = -Math.cos(rad);
  const length = Math.abs(width * dx) + Math.abs(height * dy);
  const cx = width / 2;
  const cy = height / 2;
  return {
    length,
    x1: cx - (dx * length) / 2,
    y1: cy - (dy * length) / 2,
    x2: cx + (dx * length) / 2,
    y2: cy + (dy * length) / 2,
  };
}

export function Crease({ text, accent, size = 28, style }) {
  const { colors, fonts } = useTheme();
  const gradientId = `crease${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  const [available, setAvailable] = useState(null);
  const label = String(text ?? '');
  const tones = useMemo(() => creaseTones(accent, colors.bg), [accent, colors.bg]);
  const natural = creaseWidth(label, size);
  const fitted = available != null && available < natural ? Math.floor((size * available) / natural) : size;
  const plain = fitted < FLOOR_SIZE;
  const width = creaseWidth(label, fitted);
  const height = Math.ceil((plain ? PLAIN_SIZE : fitted) * LINE_HEIGHT);
  const axis = creaseAxis(width, height);
  const stops = creaseStops(tones, axis.length);

  return (
    <View
      accessible
      accessibilityRole="header"
      accessibilityLabel={label}
      onLayout={(e) => setAvailable(e.nativeEvent.layout.width)}
      style={[{ width: natural, flexShrink: 1, minWidth: 0, overflow: 'hidden', height }, style]}
    >
      {plain ? (
        <Text
          numberOfLines={1}
          accessible={false}
          style={{ fontFamily: fonts?.sans?.semibold, fontSize: PLAIN_SIZE, lineHeight: height, color: colors.ink }}
        >
          {label}
        </Text>
      ) : (
        <Svg width={width} height={height} accessible={false} importantForAccessibility="no-hide-descendants">
          <Defs>
            <LinearGradient
              id={gradientId}
              gradientUnits="userSpaceOnUse"
              x1={axis.x1}
              y1={axis.y1}
              x2={axis.x2}
              y2={axis.y2}
            >
              {stops.map((s, i) => (
                <Stop key={i} offset={s.offset} stopColor={s.color} stopOpacity={s.opacity} />
              ))}
            </LinearGradient>
          </Defs>
          <SvgText x={0} y={fitted * BASELINE} fill={`url(#${gradientId})`} fontFamily={tokenFonts.crease} fontSize={fitted}>
            {label}
          </SvgText>
        </Svg>
      )}
    </View>
  );
}
