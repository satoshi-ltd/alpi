import { mixHex } from "../../../common/color.mjs";
import { Text, View } from 'react-native';
import { alpha, lineHeights, radii, space } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';
import { dotShape } from './dotShape';
import { useGroundTone } from './groupTone';

const TONES = {
  on: 'success',
  err: 'danger',
  warn: 'warning',
};

// Keep in step with desktop/src/primitives/Chip.jsx states.
export function Pill({ tone, children, off = false }) {
  const { colors, fonts , fontSizes} = useTheme();
  const accentKey = TONES[tone];
  const ground = useGroundTone();
  const tinted = accentKey && tone !== 'warn';
  const bg = tinted ? mixHex(colors[accentKey], 0.16, ground) : colors.hover;
  const fg = tinted ? colors[`${accentKey}Text`] : tone === 'warn' ? colors.ink : colors.ink2;
  const dot = accentKey ? colors[accentKey] : off ? colors.ink3 : null;

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s2,
        minHeight: 22,
        paddingHorizontal: space.s3,
        borderRadius: radii.tag,
        backgroundColor: bg,
        opacity: off ? alpha.muted : 1,
      }}
    >
      {dot ? <View style={{ ...dotShape('sm'), backgroundColor: dot }} /> : null}
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
