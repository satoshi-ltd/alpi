import { Pressable, Text } from 'react-native';

import { Icon } from '../../components/Icon';
import { mobile, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';

// Inverted lists scroll away from the newest message towards the past; past this offset the tail is out of sight.
export const JUMP_THRESHOLD = 800;

export function JumpToLatest({ visible, onPress }) {
  const { colors, fonts, fontSizes, shadow, chromeScale } = useTheme();
  if (!visible) return null;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel="Jump to latest"
      style={({ pressed }) => ({
        position: 'absolute',
        right: space.s7,
        bottom: space.s7,
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s3,
        paddingHorizontal: space.s6,
        height: mobile.tap,
        borderRadius: 999,
        backgroundColor: pressed ? colors.selected : colors.bgPane,
        borderWidth: 0.5,
        borderColor: colors.line2,
        ...shadow.base,
      })}
    >
      <Icon name="chev-down" size="sm" color={colors.ink2} />
      <Text maxFontSizeMultiplier={chromeScale} style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, color: colors.ink2 }}>Latest</Text>
    </Pressable>
  );
}
