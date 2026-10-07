import { contrastText, mixHex } from "../../../common/color.mjs";
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { buttonDefaults, buttonHeights, buttonVariants } from '../../../common/button.mjs';
import { radii, space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { Spinner } from './Spinner';

const SIZES = {
  sm: { padX: 12, token: 'sm' },
  md: { padX: 14, token: 'md' },
  lg: { padX: 18, token: 'lg' },
  hero: { padX: 22, token: 'xl' },
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
        : danger ? colors.danger : colors.selected;
  const fg = disabled ? colors.ink4 : quiet ? (danger ? colors.dangerText : colors.ink2)
    : danger ? colors.onDanger : primary ? (accent ? contrastText(accent) : colors.bgPane) : colors.ink;
  const bgPressed = quiet ? colors.selected : primary ? (accent ? mixHex(accent, 0.82, '#000000') : colors.ink2)
    : danger ? mixHex(colors.danger, 0.82, '#000000') : colors.line2;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled: blocked, busy: loading }}
      onPress={onPress}
      disabled={blocked}
      style={({ pressed }) => [styles.root, {
        minHeight: Button.touchHeight(size),
        paddingHorizontal: dims.padX,
        borderRadius: radii.xs,
        backgroundColor: pressed && !blocked ? bgPressed : bgIdle,
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
        <Spinner color={fg} />
      </View>}
    </Pressable>
  );
}

Button.touchHeight = (size) =>
  buttonHeights[Object.hasOwn(buttonHeights, size) ? size : buttonDefaults.mobile.size].mobile;

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
