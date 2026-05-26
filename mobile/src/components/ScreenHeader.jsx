import { Pressable, Text, View } from 'react-native';
import { space } from '../theme/tokens';

import { Icon } from './Icon';
import { useTheme } from '../theme/ThemeContext';

export function ScreenHeader({ title, subtitle, onBack, right, leadingGlyph }) {
  const { colors, fonts, fontSizes } = useTheme();
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
      {onBack ? (
        <Pressable
          onPress={onBack}
          hitSlop={space.s3}
          style={{ width: 28, height: 36, alignItems: 'center', justifyContent: 'center', marginLeft: -space.s2 }}
        >
          <Icon name="back" size={22} color={colors.ink2} strokeWidth={2} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1, minWidth: 0, flexDirection: 'column' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
          {leadingGlyph}
          <Text
            numberOfLines={1}
            style={{
              fontFamily: fonts.sans.semibold,
              fontSize: fontSizes.msg,
              lineHeight: space.s8,
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
                lineHeight: space.s6,
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
