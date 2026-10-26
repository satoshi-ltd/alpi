import { Text, View } from 'react-native';

import { space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { CountBadge } from './CountBadge';

export function AttentionPill({ count, label }) {
  return <CountBadge count={count} label={label} />;
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
