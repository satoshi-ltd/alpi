import { Pressable, Text, View } from 'react-native';
import { mobile, radii, space } from '../../theme/tokens';

import { useTheme } from '../../theme/ThemeContext';

const TARGET = { minHeight: mobile.tap, minWidth: mobile.tap, marginVertical: -space.s4, alignItems: 'center', justifyContent: 'center' };

export function PendingPeerActions({ onDiscard, onAccept }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <>
      <Pressable onPress={onDiscard} accessibilityRole="button" accessibilityLabel="Discard" style={TARGET}>
        {({ pressed }) => (
          <View style={{ paddingHorizontal: space.s5, paddingVertical: space.s2, borderRadius: radii.xs, borderWidth: 0.5, borderColor: colors.line2, backgroundColor: pressed ? colors.selected : 'transparent' }}>
            <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: colors.ink3 }}>Discard</Text>
          </View>
        )}
      </Pressable>
      <Pressable onPress={onAccept} accessibilityRole="button" accessibilityLabel="Accept" style={TARGET}>
        {({ pressed }) => (
          <View style={{ paddingHorizontal: space.s5, paddingVertical: space.s2, borderRadius: radii.xs, backgroundColor: pressed ? colors.ink2 : colors.ink }}>
            <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xs, color: colors.bgPane }}>Accept</Text>
          </View>
        )}
      </Pressable>
    </>
  );
}
