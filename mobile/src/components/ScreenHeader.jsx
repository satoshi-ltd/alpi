import { Pressable, Text, View } from 'react-native';
import { space , fontSizes} from '../theme/tokens';

import { Icon } from './Icon';
import { useTheme } from '../theme/ThemeContext';

export function ScreenHeader({ title, subtitle, onBack, right, leadingGlyph }) {
  const { colors, fonts, fontSizes, mobile } = useTheme();
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s4,
        paddingHorizontal: space.s3,
        paddingVertical: space.s3,
        borderBottomWidth: 0.5,
        borderBottomColor: colors.line,
        backgroundColor: colors.bg,
      }}
    >
      {onBack ? (
        <Pressable
          onPress={onBack}
          hitSlop={10}
          style={{ width: mobile.iconBtn, height: mobile.iconBtn, alignItems: 'center', justifyContent: 'center' }}
        >
          <Icon name="back" size={24} color={colors.ink} strokeWidth={2} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1, paddingLeft: onBack ? 0 : 12 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
          {leadingGlyph}
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xl, color: colors.ink }}>
            {title}
          </Text>
        </View>
        {subtitle ? (
          <Text
            style={{
              fontFamily: fonts.mono,
              fontSize: fontSizes.xs,
              color: colors.ink3,
              marginTop: space.s1,
              letterSpacing: 0.6,
            }}
          >
            {subtitle}
          </Text>
        ) : null}
      </View>
      {right}
    </View>
  );
}
