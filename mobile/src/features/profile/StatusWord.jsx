import { Text, View } from 'react-native';
import { radii, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';

export function StatusWord({ word, on = true, danger = false, mark = true }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View accessible={!!word} accessibilityLabel={word || undefined} style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
      {mark ? <View
        style={{
          width: 7,
          height: 7,
          borderRadius: radii.pill,
          backgroundColor: on && !danger ? colors.ink : 'transparent',
          borderWidth: on && !danger ? 0 : 1,
          borderColor: danger ? colors.danger : colors.ink4 ?? colors.ink3,
        }}
      /> : null}
      {word ? <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: danger ? colors.dangerText : mark || on ? colors.ink2 : colors.ink3 }}>{word}</Text> : null}
    </View>
  );
}
