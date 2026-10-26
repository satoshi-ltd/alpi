import { Pressable, Text, View } from 'react-native';

import { selection } from '../lib/haptics';
import { useTheme } from '../theme/ThemeContext';
import { mobile, radii } from '../theme/tokens';

const INSET = 2;

export function Segmented({ options, value, onChange, label }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel={label}
      style={{ flexDirection: 'row', padding: INSET, borderRadius: radii.xs, backgroundColor: colors.hover }}
    >
      {options.map((option) => {
        const on = option.value === value;
        return (
          <Pressable
            key={option.value}
            onPress={() => {
              if (on) return;
              selection();
              onChange?.(option.value);
            }}
            accessibilityRole="radio"
            accessibilityState={{ selected: on }}
            accessibilityLabel={option.label}
            style={{
              flex: 1,
              minHeight: mobile.tap,
              paddingHorizontal: INSET,
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: radii.xs,
              backgroundColor: on ? colors.bgPane : 'transparent',
            }}
          >
            <Text
              numberOfLines={1}
              adjustsFontSizeToFit
              minimumFontScale={0.75}
              maxFontSizeMultiplier={1.2}
              style={{ fontFamily: on ? fonts.sans.semibold : fonts.sans.regular, fontSize: fontSizes.md, color: on ? colors.ink : colors.ink2 }}
            >
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
