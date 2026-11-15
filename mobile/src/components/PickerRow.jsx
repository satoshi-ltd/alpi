import { Pressable, StyleSheet, Text, View } from 'react-native';
import { selection } from '../lib/haptics';
import { space } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';
import { PICKER_GAP, PickerLead } from './PickerLead';

const S = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center' },
  wrapWithRight: { flexDirection: 'row', alignItems: 'center', paddingRight: space.s5 },
  press: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: PICKER_GAP,
    paddingHorizontal: space.s7,
    paddingVertical: space.s6,
  },
  body: { flex: 1, gap: space.s1, minWidth: 0 },
});

export function PickerRow({
  selected = false,
  accent,
  label,
  helper,
  meta,
  right,
  onPress,
  numberOfLines = 1,
  separator = false,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const pressStyle = ({ pressed }) => [
    S.press,
    { backgroundColor: pressed ? colors.pressed : selected ? colors.selected : 'transparent' },
  ];
  return (
    <View>
    <View style={right ? S.wrapWithRight : S.wrap}>
      <Pressable
        onPress={(event) => {
          selection();
          onPress?.(event);
        }}
        accessibilityRole="button"
        accessibilityState={{ selected }}
        accessibilityLabel={typeof label === 'string' ? label : undefined}
        accessibilityHint={typeof helper === 'string' ? helper : undefined}
        android_ripple={{ color: colors.pressed }}
        style={pressStyle}
      >
        <PickerLead selected={selected} color={accent} />
        <View style={S.body}>
          {typeof label === 'string' ? (
            <Text
              numberOfLines={numberOfLines}
              style={{
                fontFamily: fonts.sans.medium,
                fontSize: fontSizes.md,
                color: colors.ink,
              }}
            >
              {label}
            </Text>
          ) : (
            label
          )}
          {helper ? (
            typeof helper === 'string' ? (
              <Text
                numberOfLines={1}
                style={{
                  fontFamily: fonts.sans.regular,
                  fontSize: fontSizes.sm,
                  color: colors.ink3,
                }}
              >
                {helper}
              </Text>
            ) : (
              helper
            )
          ) : null}
        </View>
        {meta ? <View style={{ flexShrink: 0 }}>{meta}</View> : null}
      </Pressable>
      {right ?? null}
    </View>
      {separator ? <View testID="picker-separator" style={{ height: space.s1 }} /> : null}
    </View>
  );
}
