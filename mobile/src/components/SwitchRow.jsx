import { Pressable, Text, View } from 'react-native';
import { space , fontSizes} from '../theme/tokens';

import { Switch } from './Switch';
import { useTheme } from '../theme/ThemeContext';

// Row with a label/helper on the left and a Switch on the right. Tapping anywhere on the row toggles, matching iOS Settings UX.

export function SwitchRow({ label, helper, checked, onChange, disabled }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <Pressable
      onPress={!disabled && onChange ? () => onChange(!checked) : undefined}
      android_ripple={{ color: colors.selected }}
      style={({ pressed }) => ({
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s5,
        paddingHorizontal: space.s8,
        paddingVertical: space.s6,
        backgroundColor: pressed ? colors.selected : 'transparent',
        opacity: disabled ? 0.5 : 1,
      })}
    >
      <View style={{ flex: 1, gap: space.s1 }}>
        <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.lg, color: colors.ink }}>
          {label}
        </Text>
        {helper ? (
          <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: colors.ink4 }}>
            {helper}
          </Text>
        ) : null}
      </View>
      <Switch checked={!!checked} onChange={onChange} disabled={disabled} />
    </Pressable>
  );
}
