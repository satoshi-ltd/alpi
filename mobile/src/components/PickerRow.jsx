import { Pressable, StyleSheet, Text, View } from 'react-native';
import { space , fontSizes} from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';
import { Dot } from './Dot';

const S = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center' },
  wrapWithRight: { flexDirection: 'row', alignItems: 'center', paddingRight: space.s5 },
  press: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s5,
    paddingHorizontal: space.s8,
    paddingVertical: space.s6,
  },
  dotSlot: { width: 14, alignItems: 'center' },
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
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const dotColor = accent ?? colors.ink;
  const pressStyle = ({ pressed }) => [
    S.press,
    { backgroundColor: selected || pressed ? colors.selected : 'transparent' },
  ];
  return (
    <View style={right ? S.wrapWithRight : S.wrap}>
      <Pressable onPress={onPress} android_ripple={{ color: colors.selected }} style={pressStyle}>
        <View style={S.dotSlot}>
          {selected ? <Dot color={dotColor} size={8} /> : null}
        </View>
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
                  fontFamily: fonts.mono,
                  fontSize: fontSizes.xs,
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
  );
}
