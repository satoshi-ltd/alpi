import { Text, View } from 'react-native';
import { radii, space } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';

const TRACK_W = 56;
const TRACK_H = 5;

export function clampFraction(pct) {
  const n = Number(pct);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

export function Meter({ label, value, tail, pct = 0, color, showPercent = true }) {
  const { colors, fonts, fontSizes } = useTheme();
  const fraction = clampFraction(pct);
  const percent = Math.round(fraction * 100);
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink2 }}>
        {value}
        {tail ? <Text style={{ color: colors.ink3 }}>{tail}</Text> : null}
      </Text>
      <View
        accessibilityRole="progressbar"
        accessibilityLabel={label}
        accessibilityValue={{ min: 0, max: 100, now: percent }}
        style={{
          width: TRACK_W,
          height: TRACK_H,
          borderRadius: radii.pill,
          backgroundColor: colors.line2,
          overflow: 'hidden',
        }}
      >
        <View
          style={{
            width: `${fraction * 100}%`,
            height: '100%',
            borderRadius: radii.pill,
            backgroundColor: color ?? colors.accent,
          }}
        />
      </View>
      {showPercent ? (
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
          {percent}%
        </Text>
      ) : null}
    </View>
  );
}
