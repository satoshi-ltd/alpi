import { Text, View } from 'react-native';

import { ALL_PROFILES, accessSpoken, connectionAccess } from '../../../../common/connectionAccess.mjs';
import { Fold } from '../../components/Fold';
import { profileLabel } from '../../lib/profileName';
import { nameColor } from '../../theme/name';
import { useTheme } from '../../theme/ThemeContext';
import { space, typeLeading } from '../../theme/tokens';

export function accessLabel(row, profiles) {
  return accessSpoken(connectionAccess(row, profiles), profileLabel);
}

export function AccessLine({ row, profiles, align = 'flex-start' }) {
  const { colors, fonts, fontSizes } = useTheme();
  const access = connectionAccess(row, profiles);
  const text = { fontSize: fontSizes.sm, lineHeight: Math.round(fontSizes.sm * typeLeading.small) };
  if (access.all) return <Text style={[text, { fontFamily: fonts.sans.regular, color: colors.ink2 }]}>{ALL_PROFILES}</Text>;
  return (
    <View testID="connection-access" style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: align, columnGap: space.s5, rowGap: space.s1 }}>
      {access.shown.map((entry) => (entry.known ? (
        <View key={entry.name} style={{ flexDirection: 'row', alignItems: 'center', gap: space.s1 }}>
          <Fold shape={entry.shape} color={entry.accent} size="inline" still />
          <Text style={[text, { fontFamily: fonts.sans.medium, color: nameColor(entry.accent, colors) }]}>{profileLabel(entry.name)}</Text>
        </View>
      ) : entry.known === null ? (
        <Text key={entry.name} style={[text, { fontFamily: fonts.sans.regular, color: colors.ink3 }]}>{profileLabel(entry.name)}</Text>
      ) : (
        <Text key={entry.name} style={[text, { fontFamily: fonts.sans.regular, color: colors.ink3, textDecorationLine: 'line-through' }]}>{profileLabel(entry.name)}</Text>
      )))}
      {access.more.length > 0 ? <Text style={[text, { fontFamily: fonts.sans.regular, color: colors.ink3 }]}>{`+${access.more.length}`}</Text> : null}
    </View>
  );
}
