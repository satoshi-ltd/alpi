import { Pressable, Text, View } from 'react-native';

import { mobile, space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { bannerTones } from './bannerTones';
import { Icon } from './Icon';

export function AlertBanner({ lead, detail, action, onAction }) {
  const { colors, fonts, fontSizes, mode } = useTheme();
  const { surface, text } = bannerTones('danger', colors, mode);
  return (
    <View
      accessibilityRole="alert"
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s4,
        padding: space.s5,
        backgroundColor: surface,
      }}
    >
      <Icon name="triangle-alert" size="xs" color={text} />
      <View style={{ flex: 1, minWidth: 0, gap: space.s1 }}>
        <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: colors.ink }}>{lead}</Text>
        {detail ? <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink2 }}>{detail}</Text> : null}
      </View>
      {action ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={action}
          onPress={onAction}
          style={{ minHeight: mobile.tap, minWidth: mobile.tap, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.s3 }}
        >
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.sm, color: text }}>{action}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
