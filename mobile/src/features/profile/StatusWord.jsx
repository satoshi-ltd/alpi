import { Text, View } from 'react-native';
import { space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';

export function StatusWord({ word, on = true, danger = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View accessible={!!word} accessibilityLabel={word || undefined} style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
      <View
        style={{
          width: 7,
          height: 7,
          borderRadius: 4,
          backgroundColor: on && !danger ? colors.ink : 'transparent',
          borderWidth: on && !danger ? 0 : 1,
          borderColor: danger ? colors.danger : colors.ink4 ?? colors.ink3,
        }}
      />
      {word ? <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: danger ? colors.dangerText : colors.ink2 }}>{word}</Text> : null}
    </View>
  );
}
