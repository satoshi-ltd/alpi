import { useLocalSearchParams, useRouter } from 'expo-router';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../../src/theme/tokens';

import { Row, RowGroup, RowSeparator, SectionHeader } from '../../../../../src/components/Row';
import { ScreenHeader } from '../../../../../src/components/ScreenHeader';
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

  const rows = (skills.data?.skills ?? []).map((s) => ({
    ...s,
    category: formatCategory(s.category),
  }));

  const groups = rows.reduce((m, s) => {
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
      <ScreenHeader
        title="Skills"
        subtitle={`@${id} · ${rows.length} INSTALLED`}
        onBack={goBack}
      />
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
          categoryOrder.map((cat) => (
            <View key={cat}>
              <SectionHeader>{cat}</SectionHeader>
              <RowGroup>
                {groups.get(cat).map((s, i) => (
                  <View key={s.path ?? `${s.category}/${s.name}/${i}`}>
                    {i > 0 ? <RowSeparator /> : null}
                    <Pressable
                      onPress={() =>
                        router.push({
                          pathname: `/profile/${id}/brain/skills/[name]`,
                          params: { name: s.name, path: s.path ?? '', category: s.category ?? '' },
                        })
                      }
                      android_ripple={{ color: colors.selected }}
                      style={({ pressed }) => ({
                        paddingHorizontal: space.s8,
                        paddingVertical: space.s6,
                        gap: space.s1,
                        backgroundColor: pressed ? colors.selected : 'transparent',
                      })}
                    >
                      <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink }}>
                        {s.name}
                      </Text>
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
