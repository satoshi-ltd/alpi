import { Pressable, StyleSheet, Text, View } from 'react-native';

import { radii, space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { Icon } from './Icon';

export function AlertBanner({ lead, detail, action, onAction }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View
      accessibilityRole="alert"
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s4,
        padding: space.s5,
        borderRadius: radii.xs,
        backgroundColor: colors.hover,
        borderWidth: StyleSheet.hairlineWidth,
        borderColor: colors.line,
      }}
    >
      <Icon name="triangle-alert" size="sm" color={colors.danger} />
      <View style={{ flex: 1, minWidth: 0, gap: space.s1 }}>
        <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: colors.ink }}>{lead}</Text>
        {detail ? <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>{detail}</Text> : null}
      </View>
      {action ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={action}
          onPress={onAction}
          style={{ minHeight: 44, minWidth: 44, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.s3 }}
        >
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.sm, color: colors.ink }}>{action}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
