import { mixHex } from "../../../common/color.mjs";
import { Text, View } from 'react-native';
import { alpha, lineHeights, radii, space } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';

const TONES = {
  on: 'success',
  err: 'danger',
  warn: 'warning',
};


export function Pill({ tone, children, off = false }) {
  const { colors, fonts , fontSizes} = useTheme();
  const accentKey = TONES[tone];
  const tint = accentKey ? colors[accentKey] : null;
  const bg = tint ? mixHex(tint, 0.16, colors.bgPane) : colors.hover;
  const fg = accentKey ? colors[`${accentKey}Text`] : colors.ink2;

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s2,
        minHeight: 22,
        paddingHorizontal: space.s3,
        borderRadius: radii.pill,
        backgroundColor: bg,
        opacity: off ? alpha.muted : 1,
      }}
    >
      <Text
        style={{
          fontFamily: fonts.monoMedium,
          fontSize: fontSizes.sm,
          lineHeight: fontSizes.sm * lineHeights.cozy,
          color: fg,
        }}
      >
        {children}
      </Text>
    </View>
  );
}
