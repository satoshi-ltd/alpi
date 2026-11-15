import { Pressable, Text, View } from 'react-native';
import { mobile, radii, space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';

export const ROW_PAD = { horizontal: space.s6, vertical: space.s4 };

export function PanelRow({ title, sub = null, meta = null, metaTone = null, bar = null, off = false, selected = false, onPress, accessibilityLabel }) {
  const { colors, fonts, fontSizes } = useTheme();
  const lift = selected ? colors.ink2 : colors.ink3;
  const pct = bar ? Math.max(0, Math.min(100, bar.pct)) : 0;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? [title, meta].filter(Boolean).join(', ')}
      accessibilityState={{ selected }}
      android_ripple={{ color: colors.pressed }}
      style={({ pressed }) => ({
        minHeight: mobile.tap,
        justifyContent: 'center',
        paddingHorizontal: ROW_PAD.horizontal,
        paddingVertical: ROW_PAD.vertical,
        gap: 2,
        backgroundColor: pressed ? colors.pressed : selected ? colors.selected : 'transparent',
      })}
    >
      <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: space.s2 }}>
        <Text
          numberOfLines={1}
          style={{ flex: 1, fontFamily: fonts.sans.medium, fontSize: fontSizes.md, lineHeight: Math.round(fontSizes.md * 1.34), color: off ? colors.ink2 : colors.ink }}
        >
          {title}
        </Text>
        {meta ? (
          <Text
            numberOfLines={1}
            style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, lineHeight: Math.round(fontSizes.xs * 1.34), fontVariant: ['tabular-nums'], color: metaTone === 'danger' ? colors.dangerText : lift }}
          >
            {meta}
          </Text>
        ) : null}
      </View>
      {sub ? (
        <Text numberOfLines={2} style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, lineHeight: Math.round(fontSizes.sm * 1.3), color: lift }}>
          {sub}
        </Text>
      ) : null}
      {bar ? (
        <View testID="row-bar" style={{ marginTop: space.s1, height: 3, borderRadius: radii.pill, backgroundColor: colors.line2 ?? colors.hover, overflow: 'hidden' }}>
          <View style={{ width: `${pct}%`, height: 3, backgroundColor: bar.over ? colors.danger : colors.ink2 }} />
        </View>
      ) : null}
    </Pressable>
  );
}
