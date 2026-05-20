import { Pressable, Text, View } from 'react-native';
import { radii , fontSizes} from '../../theme/tokens';

import { useTheme } from '../../theme/ThemeContext';

const TABS = [
  { id: 'all', label: 'All' },
  { id: 'alpis', label: 'Alpis' },
  { id: 'wg', label: 'Workgroups' },
];

export function SegmentedFilter({ value, onChange }) {
  const { colors, fonts, mode , fontSizes} = useTheme();
  const onBg = mode === 'dark' ? colors.bgElev : colors.bgPane;
  return (
    <View
      style={{
        flexDirection: 'row',
        padding: 2,
        backgroundColor: colors.bgInput,
        borderRadius: 9,
        gap: 0,
      }}
    >
      {TABS.map((t) => {
        const on = value === t.id;
        return (
          <Pressable
            key={t.id}
            onPress={() => onChange(t.id)}
            style={{
              flex: 1,
              paddingVertical: 7,
              paddingHorizontal: 0,
              borderRadius: radii.sm,
              alignItems: 'center',
              backgroundColor: on ? onBg : 'transparent',
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 1 },
              shadowOpacity: on ? 0.06 : 0,
              shadowRadius: on ? 2 : 0,
              elevation: on ? 1 : 0,
            }}
          >
            <Text
              style={{
                fontFamily: fonts.sans.medium,
                fontSize: fontSizes.base,
                lineHeight: 13,
                color: on ? colors.ink : colors.ink3,
              }}
            >
              {t.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
