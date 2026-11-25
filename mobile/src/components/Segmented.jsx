import { Pressable, Text, View } from 'react-native';

import { selection } from '../lib/haptics';
import { useTheme } from '../theme/ThemeContext';
import { alpha, mobile, radii, space } from '../theme/tokens';
import { focusRingStyle, useFocusRing } from './focusRing';

export const SEGMENT_INSET = space.s1;
const INSET = SEGMENT_INSET;

export function Segmented({ options, value, onChange, label }) {
  const { colors } = useTheme();
  return (
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel={label}
      style={{ flexDirection: 'row', gap: 2, padding: INSET, borderRadius: radii.pill, backgroundColor: colors.fill }}
    >
      {options.map((option) => (
        <Segment key={option.value} option={option} on={option.value === value} onChange={onChange} />
      ))}
    </View>
  );
}

function Segment({ option, on, onChange }) {
  const { colors, fonts, fontSizes, mode } = useTheme();
  const [focused, focusHandlers] = useFocusRing();
  const off = !!option.disabled && !on;
  return (
    <Pressable
      onPress={() => {
        if (on || off) return;
        selection();
        onChange?.(option.value);
      }}
      disabled={off}
      accessibilityRole="radio"
      accessibilityState={{ selected: on, disabled: off }}
      accessibilityLabel={option.spoken ?? option.label}
      {...focusHandlers}
      style={{
        opacity: off ? alpha.disabled : 1,
        flex: 1,
        minHeight: mobile.tap,
        paddingHorizontal: space.s4,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: radii.pill,
        borderWidth: 1,
        borderColor: on && mode === 'dark' ? colors.line2 : 'transparent',
        backgroundColor: on ? colors.raised : 'transparent',
        ...(on ? RAISED_CELL : null),
        ...focusRingStyle(colors, focused),
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
}

const RAISED_CELL = { shadowColor: '#000', shadowOpacity: 0.12, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 };
