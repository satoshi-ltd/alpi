import { Pressable } from 'react-native';
import { mobile, radii, space } from '../theme/tokens';

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
        marginTop: -space.s2,
        marginRight: -space.s3,
        borderRadius: radii.pill,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.selected : 'transparent',
        ...style,
      })}
    >
      <Icon name="x" size="lg" color={color ?? colors.ink3} />
    </Pressable>
  );
}
