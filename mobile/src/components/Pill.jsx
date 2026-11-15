import { mixHex } from "../../../common/color.mjs";
import { Text, View } from 'react-native';
import { alpha, controlRole, radii, space, typeLeading } from '../theme/tokens';

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
  const bg = tinted ? mixHex(colors[accentKey], 0.16, ground) : ground === colors.fill || ground === colors.card ? colors.bgPane : colors.fill;
  const fg = tinted ? colors[`${accentKey}Text`] : tone === 'warn' ? colors.ink : colors.ink2;
  const dot = accentKey ? colors[accentKey] : off ? colors.ink3 : null;

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s2,
        minHeight: controlRole.compact,
        paddingHorizontal: space.s4,
        borderRadius: radii.pill,
        backgroundColor: bg,
        opacity: off ? alpha.muted : 1,
      }}
    >
      {dot ? <View style={{ ...dotShape('md'), backgroundColor: dot }} /> : null}
      <Text
        style={{
          fontFamily: fonts.sans.medium,
          fontSize: fontSizes.sm,
          lineHeight: Math.round(fontSizes.sm * typeLeading.small),
          color: fg,
        }}
      >
        {children}
      </Text>
    </View>
  );
}
