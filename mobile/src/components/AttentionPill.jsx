import { Text, View } from 'react-native';

import { radii, space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';

export function AttentionPill({ count, label }) {
  const { colors, fonts, fontSizes } = useTheme();
  if (!count) return null;
  return (
    <View
      accessible
      accessibilityLabel={label}
      style={{ minWidth: 20, minHeight: 20, paddingHorizontal: space.s2, borderRadius: radii.xs, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.danger }}
    >
      <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: colors.onDanger }}>{count}</Text>
    </View>
  );
}

export function AttentionValue({ count, label, children }) {
  const { colors, fonts, fontSizes } = useTheme();
  if (!count) return children;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
      <AttentionPill count={count} label={label} />
      <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3 }}>{children}</Text>
    </View>
  );
}
