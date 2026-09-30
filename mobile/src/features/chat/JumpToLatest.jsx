import { Pressable, Text } from 'react-native';
import Animated, { useAnimatedStyle } from 'react-native-reanimated';

import { Icon } from '../../components/Icon';
import { usePresence } from '../../lib/usePresence';
import { mobile, motionMs, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';

// Inverted lists scroll away from the newest message towards the past; past this offset the tail is out of sight.
export const JUMP_THRESHOLD = 800;
const JUMP_RISE = space.s3;

export function JumpToLatest({ visible, onPress }) {
  const { colors, fonts, fontSizes, shadow, chromeScale } = useTheme();
  const { mounted, progress } = usePresence(visible, motionMs.jump);
  const fade = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ translateY: JUMP_RISE * (1 - progress.value) }],
  }));
  if (!mounted) return null;
  return (
    <Animated.View
      testID="jump-to-latest"
      pointerEvents={visible ? 'box-none' : 'none'}
      style={[{ position: 'absolute', right: space.s7, bottom: space.s7 }, fade]}
    >
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel="Jump to latest"
        style={({ pressed }) => ({
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
    </Animated.View>
  );
}
