import { Pressable, Text, View } from 'react-native';

import { lineHeights, mobile, space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { Button } from './Button';

export function LoadFailed({ label, error, onRetry, inline = false, showDetail = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  const message = `Couldn't load ${label}`;
  const detail = error ? String(error?.message ?? error) : null;
  if (inline) {
    return (
      <View accessibilityRole="alert" style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4, paddingHorizontal: space.s8, paddingVertical: space.s6 }}>
        <View style={{ flex: 1, gap: space.s1 }}>
          <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.dangerText }}>{message}</Text>
          {showDetail && detail ? (
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, lineHeight: fontSizes.xs * lineHeights.cozy, color: colors.ink3 }}>{detail}</Text>
          ) : null}
        </View>
        {onRetry ? (
          <Pressable onPress={onRetry} accessibilityRole="button" accessibilityLabel="Retry" style={{ minHeight: mobile.tap, minWidth: mobile.tap, marginVertical: -space.s5, alignItems: 'center', justifyContent: 'center' }}>
            <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.ink2 }}>Retry</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }
  return (
    <View accessibilityRole="alert" style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s10, gap: space.s5 }}>
      <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink, textAlign: 'center' }}>{message}</Text>
      {detail ? (
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, lineHeight: fontSizes.xs * lineHeights.cozy, color: colors.ink3, textAlign: 'center' }}>
          {detail}
        </Text>
      ) : null}
      {onRetry ? <Button title="Retry" size="md" onPress={onRetry} /> : null}
    </View>
  );
}
