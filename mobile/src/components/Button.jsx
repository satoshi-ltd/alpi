import { contrastText } from "../../../common/color.mjs";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { buttonDefaults, buttonHeights, buttonVariants } from '../../../common/button.mjs';
import { space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';

const SIZES = {
  sm: { padX: 12, radius: 10, token: 'sm' },
  md: { padX: 14, radius: 10, token: 'md' },
  lg: { padX: 18, radius: 14, token: 'lg' },
  hero: { padX: 22, radius: 14, token: 'xl' },
};

export function Button({
  title,
  onPress,
  variant = buttonDefaults.mobile.variant,
  size = buttonDefaults.mobile.size,
  fullWidth = false,
  loading = false,
  disabled = false,
  accent,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  variant = buttonVariants.includes(variant) ? variant : buttonDefaults.mobile.variant;
  size = Object.hasOwn(buttonHeights, size) ? size : buttonDefaults.mobile.size;
  const dims = SIZES[size];
  const blocked = disabled || loading;
  const quiet = variant === 'ghost' || variant === 'danger-ghost';
  const primary = variant === 'primary';
  const danger = variant === 'danger' || variant === 'danger-ghost';
  const bgIdle = disabled ? (quiet ? 'transparent' : colors.bgInput)
    : quiet ? 'transparent'
      : primary ? accent ?? colors.ink
        : danger ? colors.danger : colors.hover;
  const fg = disabled ? colors.ink4 : quiet ? (danger ? colors.dangerText : colors.ink2)
    : danger ? colors.onDanger : primary ? (accent ? contrastText(accent) : colors.bgPane) : colors.ink;
  const bgPressed = quiet ? colors.selected : primary ? colors.ink2
    : danger ? colors.danger : colors.selected;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled: blocked, busy: loading }}
      onPress={onPress}
      disabled={blocked}
      style={({ pressed }) => [styles.root, {
        minHeight: buttonHeights[size].mobile,
        paddingHorizontal: dims.padX,
        borderRadius: dims.radius,
        backgroundColor: pressed && !blocked ? bgPressed : bgIdle,
        opacity: pressed && !blocked ? 0.85 : 1,
        alignSelf: fullWidth ? 'stretch' : 'auto',
      }]}
    >
      <Text style={[
        styles.label,
        {
          fontFamily: fonts.sans[quiet ? 'medium' : 'semibold'],
          fontSize: fontSizes[dims.token],
          lineHeight: fontSizes[dims.token],
          color: fg,
        },
        loading && styles.hiddenLabel,
      ]}>
        {title}
      </Text>
      {loading && <View style={styles.progress} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <ActivityIndicator color={fg} />
      </View>}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    paddingVertical: space.s2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: { textAlign: 'center' },
  hiddenLabel: { opacity: 0 },
  progress: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
