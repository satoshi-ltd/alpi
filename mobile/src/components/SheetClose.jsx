import { Pressable } from 'react-native';
import { lineHeights, mobile, radii, space, typeLadder, typography } from '../theme/tokens';

export const SHEET_CLOSE_BLEED = Math.round((mobile.tap - typeLadder.title * lineHeights[typography.dialogTitle.leading]) / 2);

import { Icon } from './Icon';
import { useTheme } from '../theme/ThemeContext';

export function SheetClose({ onPress, color, hint = 'Dismisses this sheet — you can also swipe it down', style }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel="Close"
      accessibilityHint={hint}
      hitSlop={space.s3}
      style={({ pressed }) => ({
        width: mobile.tap,
        height: mobile.tap,
        marginTop: -SHEET_CLOSE_BLEED,
        marginRight: -SHEET_CLOSE_BLEED,
        borderRadius: radii.pill,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.pressed : 'transparent',
        ...style,
      })}
    >
      <Icon name="x" size="md" color={color ?? colors.ink3} />
    </Pressable>
  );
}
