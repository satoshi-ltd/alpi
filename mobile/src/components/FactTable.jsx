import { Text, View } from 'react-native';
import { space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { code } from '../theme/code';

export const FACT_LABEL_W = 72;

export function FactCode({ children, quiet = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  return <Text style={{ ...code(fonts, fontSizes.sm), color: quiet ? colors.ink3 : colors.ink2 }}>{children}</Text>;
}

export function FactTable({ rows }) {
  const { colors, fonts, fontSizes } = useTheme();
  const shown = rows.filter((r) => r && r.value != null && r.value !== '' && r.value !== false);
  if (!shown.length) return null;
  const line = Math.round(fontSizes.sm * 1.43);
  return (
    <View>
      {shown.map((r) => (
        <View key={r.label} style={{ flexDirection: 'row', gap: space.s4, paddingVertical: space.s1, alignItems: 'baseline' }}>
          <Text style={{ width: FACT_LABEL_W, fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, lineHeight: line, color: colors.ink3 }}>{r.label}</Text>
          <View style={{ flex: 1, minWidth: 0 }}>
            {r.block ? r.value : (
              <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, lineHeight: line, color: r.tone === 'danger' ? colors.dangerText : colors.ink2 }}>{r.value}</Text>
            )}
          </View>
        </View>
      ))}
    </View>
  );
}
