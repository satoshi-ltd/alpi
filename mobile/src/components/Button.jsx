import { ActivityIndicator, Pressable, Text } from 'react-native';
import { fontSizes } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';

const SIZES = {
  md: { h: 40, padX: 14, radius: 10, fontSize: fontSizes.md, ghostFontSize: 14, weightFilled: 'semibold', weightGhost: 'medium' },
  lg: { h: 48, padX: 18, radius: 14, fontSize: fontSizes.msg, ghostFontSize: 15, weightFilled: 'semibold', weightGhost: 'medium' },
  hero: { h: 56, padX: 22, radius: 14, fontSize: fontSizes.xl, ghostFontSize: 16, weightFilled: 'semibold', weightGhost: 'medium' },
};

export function Button({
  title,
  onPress,
  variant = 'primary',
  size = 'lg',
  fullWidth = false,
  loading = false,
  disabled = false,
  accent,
}) {
  const { colors, fonts , fontSizes} = useTheme();
  const dims = SIZES[size] ?? SIZES.lg;

  const isPrimary = variant === 'primary';
  const isGhost = variant === 'ghost';
  const isDanger = variant === 'danger';

  const bgIdle = disabled
    ? isGhost
      ? 'transparent'
      : colors.bgInput
    : isPrimary
      ? accent ?? colors.ink
      : isDanger
        ? colors.danger
        : isGhost
          ? 'transparent'
          : colors.hover;

  const fg = disabled
    ? colors.ink4
    : isPrimary || isDanger
      ? colors.bgPane
      : isGhost
        ? colors.ink2
        : colors.ink;

  const family = isGhost
    ? fonts.sans[dims.weightGhost]
    : fonts.sans[dims.weightFilled];
  const fontSize = isGhost ? dims.ghostFontSize : dims.fontSize;

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => ({
        height: dims.h,
        paddingHorizontal: dims.padX,
        borderRadius: dims.radius,
        backgroundColor:
          pressed && !disabled
            ? isPrimary
              ? colors.ink2
              : isDanger
                ? '#a83a3a'
                : colors.selected
            : bgIdle,
        alignItems: 'center',
        justifyContent: 'center',
        alignSelf: fullWidth ? 'stretch' : 'auto',
      })}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <Text
          style={{
            fontFamily: family,
            fontSize,
            lineHeight: fontSize,
            color: fg,
          }}
        >
          {title}
        </Text>
      )}
    </Pressable>
  );
}
