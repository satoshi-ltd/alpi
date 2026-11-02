import { Platform, Pressable, Text, View } from 'react-native';

import { Icon } from '../../components/Icon';
import { RowGroup, RowSeparator } from '../../components/Row';
import { mobile, radii, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';

export const ALP_SCOPES = [
  { id: 'link.ping', desc: 'liveness probe · zero LLM cost' },
  { id: 'link.ask', desc: 'full agent turn · spends from your daily LLM budget' },
  { id: 'link.cancel', desc: 'abort an in-flight ask the peer started' },
];

const BOX = 22;

function Check({ on }) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        width: BOX,
        height: BOX,
        borderRadius: radii.xs,
        borderWidth: 1.5,
        borderColor: on ? colors.ink : colors.ink3,
        backgroundColor: on ? colors.ink : 'transparent',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {on ? <Icon name="check" size="xs" color={colors.bgPane} /> : null}
    </View>
  );
}

export function ScopeToggles({ value, onToggle }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <RowGroup style={{ marginHorizontal: 0 }}>
      {ALP_SCOPES.map((s, i) => {
        const on = value.has(s.id);
        return (
          <View key={s.id}>
            {i > 0 ? <RowSeparator indent={space.s7 + BOX + space.s5} /> : null}
            <Pressable
              onPress={() => onToggle(s.id)}
              accessibilityRole="checkbox"
              accessibilityState={{ checked: on }}
              accessibilityLabel={`${s.id}, ${s.desc}`}
              android_ripple={{ color: colors.selected }}
              style={({ pressed }) => ({
                flexDirection: 'row',
                alignItems: 'center',
                gap: space.s5,
                minHeight: mobile.tap,
                paddingHorizontal: space.s7,
                paddingVertical: space.s4,
                backgroundColor: pressed && Platform.OS !== 'android' ? colors.selected : 'transparent',
              })}
            >
              <Check on={on} />
              <View style={{ flex: 1, gap: space.s1 }}>
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink }}>{s.id}</Text>
                <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink3 }}>{s.desc}</Text>
              </View>
            </Pressable>
          </View>
        );
      })}
    </RowGroup>
  );
}
