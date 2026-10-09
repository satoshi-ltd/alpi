import { Pressable, ScrollView, Text, View } from 'react-native';
import { mobile, radii, space } from '../../theme/tokens';

import { Eyebrow } from '../../components/Eyebrow';
import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';
import { JUMP_SECTIONS, summaryRows } from './jumpSections';

export function JumpChips({ current, onJump }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ borderBottomWidth: 0.5, borderBottomColor: colors.line, backgroundColor: colors.bg }}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: space.s5, gap: space.s1 }}>
        {JUMP_SECTIONS.map((section) => {
          const on = section.id === current;
          return (
            <Pressable
              key={section.id}
              onPress={() => onJump(section.id)}
              accessibilityRole="button"
              accessibilityLabel={`Go to ${section.label}`}
              accessibilityState={{ selected: on }}
              style={{ minHeight: mobile.tap, paddingHorizontal: space.s5, justifyContent: 'center', borderRadius: radii.xs, backgroundColor: on ? colors.selected : 'transparent' }}
            >
              <Text style={{ fontFamily: on ? fonts.sans.semibold : fonts.sans.regular, fontSize: fontSizes.md, color: on ? colors.ink : colors.ink2 }}>{section.label}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

export function AttentionSummary({ att, onJump }) {
  const { colors, fonts, fontSizes } = useTheme();
  const rows = summaryRows(att);
  if (!rows.length) return null;
  return (
    <View accessibilityRole="summary" style={{ marginHorizontal: space.s6, marginTop: space.s6, paddingTop: space.s5, paddingHorizontal: space.s7, borderRadius: radii.xs, backgroundColor: colors.hover }}>
      <Eyebrow color={colors.warningText ?? colors.warning}>{`Needs you · ${rows.length}`}</Eyebrow>
      {rows.map((row) => (
        <Pressable
          key={row.id}
          onPress={() => onJump(row.section)}
          accessibilityRole="button"
          accessibilityLabel={`${row.text}, ${row.label}`}
          style={{ minHeight: mobile.tap, flexDirection: 'row', alignItems: 'center', gap: space.s4 }}
        >
          <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: colors.danger }} />
          <Text style={{ flex: 1, fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink }}>{row.text}</Text>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{row.label}</Text>
          <Icon name="chevron-right" size="xs" color={colors.ink4} />
        </Pressable>
      ))}
    </View>
  );
}
