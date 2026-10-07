import { useLocalSearchParams, useRouter } from 'expo-router';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../../src/theme/tokens';

import { Dot } from '../../../../../src/components/Dot';
import { useAttention } from '../../../../../src/hooks/useAttention';
import { skillItem, skillWord } from '../../../../../../common/attention.mjs';
import { Row, RowGroup, RowSeparator, SectionHeader } from '../../../../../src/components/Row';
import { PanelHeader } from '../../../../../src/features/profile/PanelHeader';
import { useBack } from '../../../../../src/hooks/useBack';
import { useSkills } from '../../../../../src/hooks/useDaemonData';
import { usePullRefresh } from '../../../../../src/hooks/usePullRefresh';
import { useTheme } from '../../../../../src/theme/ThemeContext';
import { LoadFailed } from '../../../../../src/components/LoadFailed';
import { EMPTY } from '../../../../../../common/emptyCopy.mjs';

function formatCategory(raw) {
  if (!raw) return 'Uncategorized';
  return raw.charAt(0).toUpperCase() + raw.slice(1).replace(/-/g, ' ');
}

export default function SkillsList() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const { colors, fonts, fontSizes } = useTheme();
  const pull = usePullRefresh(() => skills.refresh?.());
  const skills = useSkills(id);
  const { att } = useAttention(id);

  const rows = (skills.data?.skills ?? []).map((s) => ({
    ...s,
    flag: skillItem(att, s.category, s.name),
    rawCategory: s.category ?? '',
    category: formatCategory(s.category),
  }));
  const needs = rows.filter((s) => s.flag);

  const groups = rows.filter((s) => !s.flag).reduce((m, s) => {
    const k = s.category;
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(s);
    return m;
  }, new Map());
  const categoryOrder = [
    ...[...groups.keys()].filter((c) => c !== 'Uncategorized').sort(),
    ...(groups.has('Uncategorized') ? ['Uncategorized'] : []),
  ];

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <PanelHeader profile={id} section="SKILLS" count={rows.length} onBack={goBack} />
      <ScrollView refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />} contentContainerStyle={{ paddingBottom: space.s9 }}>
        {skills.loading && rows.length === 0 ? (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : skills.error && rows.length === 0 ? (
          <LoadFailed inline label="skills" error={skills.error} onRetry={() => skills.refresh?.()} />
        ) : rows.length === 0 ? (
          <RowGroup style={{ marginTop: space.s5 }}>
            <Row label={EMPTY.skills.title} helper={EMPTY.skills.hint} chevron={false} />
          </RowGroup>
        ) : (
          [...(needs.length ? [['Needs you', needs]] : []), ...categoryOrder.map((cat) => [cat, groups.get(cat)])].map(([cat, list]) => (
            <View key={cat}>
              <SectionHeader>{cat === 'Needs you' ? `Needs you · ${list.length}` : cat}</SectionHeader>
              <RowGroup>
                {list.map((s, i) => (
                  <View key={s.path ?? `${s.category}/${s.name}/${i}`}>
                    {i > 0 ? <RowSeparator /> : null}
                    <Pressable
                      onPress={() =>
                        router.push({
                          pathname: `/profile/${id}/brain/skills/[name]`,
                          params: { name: s.name, path: s.path ?? '', category: s.rawCategory },
                        })
                      }
                      android_ripple={{ color: colors.selected }}
                      style={({ pressed }) => ({
                        minHeight: 44,
                        paddingHorizontal: space.s8,
                        paddingVertical: space.s6,
                        gap: space.s1,
                        backgroundColor: pressed ? colors.selected : 'transparent',
                      })}
                    >
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
                        {s.flag ? <Dot color={colors.danger} /> : null}
                        <Text style={{ flex: 1, fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink }} numberOfLines={1}>
                          {s.name}
                        </Text>
                        {s.flag ? (
                          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.dangerText }}>{skillWord(s.flag)}</Text>
                        ) : s.status && s.status !== 'active' ? (
                          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: s.status === 'invalid' ? colors.dangerText : colors.ink3 }}>
                            {s.status}
                          </Text>
                        ) : null}
                      </View>
                      {s.description ? (
                        <Text
                          numberOfLines={2}
                          style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}
                        >
                          {s.description}
                        </Text>
                      ) : null}
                    </Pressable>
                  </View>
                ))}
              </RowGroup>
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
