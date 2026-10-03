import { Pressable, Text, View } from 'react-native';

import { NOTIFICATION_FILTERS } from '../../../../common/notificationTriage.mjs';
import { useTheme } from '../../theme/ThemeContext';
import { mobile, radii, space } from '../../theme/tokens';

const INSET = 2;

export function TriageFilters({ filter, counts, onFilter }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ gap: space.s3, paddingTop: space.s3, paddingBottom: space.s2 }}>
      <View
        accessibilityRole="tablist"
        style={{ flexDirection: 'row', marginHorizontal: space.s5, padding: INSET, borderRadius: radii.xs, backgroundColor: colors.hover }}
      >
        {NOTIFICATION_FILTERS.map((f) => {
          const on = filter === f.id;
          return (
            <Pressable
              key={f.id}
              onPress={() => onFilter(f.id)}
              accessibilityRole="tab"
              accessibilityState={{ selected: on }}
              accessibilityLabel={`${f.label}, ${counts[f.id]}`}
              hitSlop={{ top: INSET, bottom: INSET }}
              style={{
                flex: 1,
                minHeight: mobile.tap - 2 * INSET,
                paddingHorizontal: space.s2,
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: radii.xs,
                backgroundColor: on ? colors.bgPane : 'transparent',
              }}
            >
              <Text style={{ textAlign: 'center', fontFamily: on ? fonts.sans.semibold : fonts.sans.regular, fontSize: fontSizes.sm, color: on ? colors.ink : colors.ink3 }}>
                {f.label}
                {f.id === 'all' ? '' : <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs }}>{` ${counts[f.id]}`}</Text>}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
