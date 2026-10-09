import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { space } from '../../theme/tokens';

import { Row, RowGroup, RowSeparator, SectionHeader } from '../../components/Row';
import { Eyebrow } from '../../components/Eyebrow';
import { useTools } from '../../hooks/useDaemonData';
import { usePullRefresh } from '../../hooks/usePullRefresh';
import { useTheme } from '../../theme/ThemeContext';
import { LoadFailed } from '../../components/LoadFailed';
import { EMPTY } from '../../../../common/emptyCopy.mjs';
import { ListSkeleton } from '../../components/ListSkeleton';

// Same category order as desktop ToolsPanel.
const CATEGORY_ORDER = [
  'Filesystem',
  'Workspace',
  'Web',
  'Memory',
  'Comms',
  'Agent',
  'Media',
  'System',
  'Collab',
];

export function groupTools(toolList) {
  const rows = toolList ?? [];
  const groups = rows.reduce((m, t) => {
    const k = t.category ?? 'Other';
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(t);
    return m;
  }, new Map());
  const cats = [
    ...CATEGORY_ORDER.filter((c) => groups.has(c)),
    ...[...groups.keys()].filter((c) => !CATEGORY_ORDER.includes(c)).sort(),
  ];
  return { rows, groups, cats, ordered: cats.flatMap((cat) => groups.get(cat)) };
}

export function ToolsList({ profile: id, selectedName = null, onOpen }) {
  const { colors, fonts, fontSizes } = useTheme();
  const pull = usePullRefresh(() => tools.refresh?.());
  const tools = useTools(id);
  const { rows, groups, cats } = groupTools(tools.data?.tools);

  return (
    <>
      <ScrollView refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />} contentContainerStyle={{ paddingBottom: space.s9 }}>
        {tools.loading && rows.length === 0 ? (
          <ListSkeleton rows={4} helper="sm" label="Loading tools" style={{ marginTop: space.s5 }} />
        ) : tools.error && rows.length === 0 ? (
          <LoadFailed inline label="tools" error={tools.error} onRetry={() => tools.refresh?.()} />
        ) : rows.length === 0 ? (
          <RowGroup style={{ marginTop: space.s5 }}>
            <Row label={EMPTY.tools.title} helper={EMPTY.tools.hint} chevron={false} />
          </RowGroup>
        ) : (
          cats.map((cat) => (
            <View key={cat}>
              <SectionHeader>{cat}</SectionHeader>
              <RowGroup>
                {groups.get(cat).map((t, i) => (
                  <View key={t.name}>
                    {i > 0 ? <RowSeparator /> : null}
                    <Pressable
                      onPress={() => onOpen(t)}
                      android_ripple={{ color: colors.selected }}
                      style={({ pressed }) => ({
                        paddingHorizontal: space.s8,
                        paddingVertical: space.s6,
                        gap: space.s1,
                        backgroundColor: pressed || t.name === selectedName ? colors.selected : 'transparent',
                      })}
                    >
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
                        <Text
                          style={{
                            fontFamily: fonts.monoMedium,
                            fontSize: fontSizes.lg,
                            color: t.denied ? colors.ink3 : colors.ink,
                            textDecorationLine: t.denied ? 'line-through' : 'none',
                          }}
                        >
                          {t.name}
                        </Text>
                        {t.denied ? (
                          <Eyebrow color={colors.warning}>denied</Eyebrow>
                        ) : null}
                      </View>
                      {t.description ? (
                        <Text
                          numberOfLines={2}
                          style={{
                            fontFamily: fonts.sans.regular,
                            fontSize: fontSizes.sm,
                            color: colors.ink3,
                            opacity: t.denied ? 0.6 : 1,
                          }}
                        >
                          {t.description}
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
    </>
  );
}
