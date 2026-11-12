import { Text, View } from 'react-native';

import { badgeCount, countBadgeSpec } from '../../../common/countBadge.mjs';
import { countBadge, space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';

export function countBadgeText(fonts, color) {
  return {
    fontFamily: fonts.monoSemibold,
    fontSize: countBadge.fontSize,
    lineHeight: countBadge.fontSize,
    includeFontPadding: false,
    color,
  };
}

export function CountBadge({ count, label, tone }) {
  const { colors, fonts } = useTheme();
  if (!(count > 0)) return null;
  return (
    <View
      accessible={label ? true : undefined}
      accessibilityLabel={label}
      style={{
        minWidth: countBadgeSpec.size.mobile,
        height: countBadgeSpec.size.mobile,
        paddingHorizontal: space.s1,
        flexDirection: 'row',
        borderRadius: countBadge.radius,
        backgroundColor: tone ?? colors.danger,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Text allowFontScaling={false} style={countBadgeText(fonts, colors.onDanger ?? '#fff')}>
        {badgeCount(count)}
      </Text>
    </View>
  );
}
