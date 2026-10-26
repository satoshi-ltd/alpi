import { Pressable, Text, View } from 'react-native';
import { mobile, space } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';
import { Dot } from './Dot';
import { Icon } from './Icon';

const TONE = {
  danger: 'danger',
  warning: 'warning',
  info: 'ink3',
  success: 'success',
};

const ICON_KINDS = new Set(['danger', 'warning']);

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
  const { colors, fonts, fontSizes } = useTheme();
  const tint = colors[TONE[kind]] ?? colors.ink3;
  const textTint = colors[`${TONE[kind]}Text`] ?? colors.ink3;
  return (
    <View
      accessibilityRole={kind === 'danger' ? 'alert' : undefined}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s4,
        paddingLeft: space.s7,
        paddingRight: space.s4,
        paddingVertical: space.s2,
        backgroundColor: `${tint}1f`,
      }}
    >
      {ICON_KINDS.has(kind) ? <Icon name="triangle-alert" size="xs" color={tint} /> : <Dot color={tint} />}
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
      {action ? <BannerAction label={action} onPress={onAction} color={textTint} /> : null}
    </View>
  );
}
