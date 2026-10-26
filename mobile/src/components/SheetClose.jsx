import { Pressable } from 'react-native';
import { mobile, radii, space } from '../theme/tokens';

export const SHEET_CLOSE_BLEED = space.s4;

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
        borderRadius: radii.xs,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.selected : 'transparent',
        ...style,
      })}
    >
      <Icon name="x" size="md" color={color ?? colors.ink3} />
    </Pressable>
  );
}
