import { Pressable, Text, View } from 'react-native';
import { mobile, space } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';
import { LEAD_DOT, bannerTones } from './bannerTones';
import { Dot } from './Dot';
import { Icon } from './Icon';

function BannerAction({ label, onPress, color }) {
  const { fonts, fontSizes } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={{ minHeight: mobile.tap, minWidth: mobile.tap, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.s3 }}
    >
      <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color }}>{label}</Text>
    </Pressable>
  );
}

export function Banner({ kind = 'info', children, action, onAction, secondaryAction, onSecondaryAction }) {
  const { colors, fonts, fontSizes, mode } = useTheme();
  const { tone, surface, text, lead } = bannerTones(kind, colors, mode);
  return (
    <View
      accessibilityRole={tone === 'danger' ? 'alert' : undefined}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s4,
        paddingLeft: space.s7,
        paddingRight: space.s4,
        paddingVertical: space.s2,
        backgroundColor: surface,
      }}
    >
      {LEAD_DOT[tone] ? <Dot color={lead} /> : <Icon name="triangle-alert" size="xs" color={lead} />}
      <Text
        style={{
          flex: 1,
          fontFamily: fonts.sans.medium,
          fontSize: fontSizes.md,
          color: colors.ink2,
        }}
      >
        {children}
      </Text>
      {secondaryAction ? <BannerAction label={secondaryAction} onPress={onSecondaryAction} color={colors.ink2} /> : null}
      {action ? <BannerAction label={action} onPress={onAction} color={text} /> : null}
    </View>
  );
}
