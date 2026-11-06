import { contrastText, mixHex } from "../../../common/color.mjs";
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { buttonAccentPressed, buttonDefaults, buttonHeights, buttonLabelWeight, buttonPressed, buttonVariants } from '../../../common/button.mjs';
import { alpha, radii, space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { Spinner } from './Spinner';

const SIZES = {
  sm: { padX: space.s5, token: 'sm' },
  md: { padX: space.s6, token: 'md' },
  lg: { padX: space.s8, token: 'lg' },
  hero: { padX: space.s9, token: 'xl' },
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
  const bgIdle = quiet ? 'transparent'
    : primary ? accent ?? colors.ink
      : danger ? colors.danger : colors.selected;
  const fg = quiet ? (danger ? colors.dangerText : colors.ink2)
    : danger ? colors.onDanger : primary ? (accent ? contrastText(accent) : colors.bgPane) : colors.ink;
  const bgPressed = pressedColor(variant, colors, primary ? accent : null);

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
        ...(disabled && !loading ? { opacity: alpha.disabled } : {}),
        alignSelf: fullWidth ? 'stretch' : 'auto',
      }]}
    >
      <View style={styles.content}>
        {loading && <View pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <Spinner color={fg} />
        </View>}
        <Text style={[
          styles.label,
          {
            fontFamily: fonts.sans[buttonLabelWeight[variant]],
            fontSize: fontSizes[dims.token],
            lineHeight: fontSizes[dims.token],
            color: fg,
          },
        ]}>
          {title}
        </Text>
      </View>
    </Pressable>
  );
}

function pressedColor(variant, colors, accent) {
  if (accent) return mixHex(accent, buttonAccentPressed.amount, '#000000');
  const recipe = buttonPressed[variant];
  if (recipe.token) return colors[recipe.token];
  const toward = recipe.toward === 'black' ? '#000000' : colors.bgPane;
  return mixHex(colors[recipe.from], recipe.amount, toward);
}

Button.touchHeight = (size) =>
  buttonHeights[Object.hasOwn(buttonHeights, size) ? size : buttonDefaults.mobile.size].mobile;

const styles = StyleSheet.create({
  root: {
    paddingVertical: space.s2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.s3 },
  label: { textAlign: 'center', flexShrink: 1 },
});
