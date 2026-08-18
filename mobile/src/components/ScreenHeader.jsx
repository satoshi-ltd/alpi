import { Pressable, Text, View } from 'react-native';
import { lineHeights, space } from '../theme/tokens';

import { Icon } from './Icon';
import { useShowBack } from '../hooks/useShowBack';
import { useTheme } from '../theme/ThemeContext';

export function ScreenHeader({ title, subtitle, onBack, right, leadingGlyph }) {
  const { colors, fonts, fontSizes } = useTheme();
  const showBack = useShowBack(onBack);
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s4,
        paddingHorizontal: space.s5,
        paddingTop: space.s3,
        paddingBottom: space.s5,
        backgroundColor: colors.bg,
        borderBottomWidth: 0.5,
        borderBottomColor: colors.line,
      }}
    >
      {showBack ? (
        <Pressable
          onPress={onBack}
          hitSlop={space.s3}
          style={{ width: 28, height: 36, alignItems: 'center', justifyContent: 'center', marginLeft: -space.s2 }}
        >
          <Icon name="back" size="lg" color={colors.ink2} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1, minWidth: 0, flexDirection: 'column' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
          {leadingGlyph}
          <Text
            numberOfLines={1}
            style={{
              fontFamily: fonts.sans.semibold,
              fontSize: fontSizes.xl,
              lineHeight: fontSizes.xl * lineHeights.cozy,
              color: colors.ink,
            }}
          >
            {title}
          </Text>
        </View>
        {subtitle ? (
          typeof subtitle === 'string' ? (
            <Text
              numberOfLines={1}
              style={{
                fontFamily: fonts.mono,
                fontSize: fontSizes.xs,
                lineHeight: fontSizes.xs * lineHeights.cozy,
                color: colors.ink3,
              }}
            >
              {subtitle}
            </Text>
          ) : (
            <View>{subtitle}</View>
          )
        ) : null}
      </View>
      {right}
    </View>
  );
}
