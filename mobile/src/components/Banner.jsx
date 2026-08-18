import { Pressable, Text, View } from 'react-native';
import { space } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';
import { Dot } from './Dot';

const TONE = {
  danger: 'danger',
  warning: 'warning',
  info: 'ink3',
};

export function Banner({ kind = 'info', children, action, onAction, pulse }) {
  const { colors, fonts, fontSizes } = useTheme();
  const tint = colors[TONE[kind]] ?? colors.ink3;
  const showPulse = pulse ?? (kind === 'danger' || kind === 'warning');
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s4,
        paddingHorizontal: space.s7,
        paddingVertical: space.s4,
        backgroundColor: `${tint}1f`,
      }}
    >
      <Dot color={tint} />
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
      {action ? (
        <Pressable onPress={onAction} hitSlop={6}>
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: tint }}>
            {action}
          </Text>
        </Pressable>
      ) : null}
      {showPulse ? null : null}
    </View>
  );
}
