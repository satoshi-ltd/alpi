import { RefreshControl, ScrollView, View } from 'react-native';
import { space } from '../../theme/tokens';

import { Row, RowGroup, RowSeparator, SectionHeader } from '../../components/Row';
import { PanelRow } from '../../components/PanelRow';
import { firstSentence } from '../../../../common/panelRow.mjs';
import { useTools } from '../../hooks/useDaemonData';
import { usePullRefresh } from '../../hooks/usePullRefresh';
import { useTheme } from '../../theme/ThemeContext';
import { LoadFailed } from '../../components/LoadFailed';
import { EMPTY } from '../../../../common/emptyCopy.mjs';
import { useSkeleton } from '../../hooks/useSkeleton';
import { useReveal } from '../../hooks/useReveal';
import { FadeIn } from '../../components/FadeIn';
import { ListSkeleton } from '../../components/ListSkeleton';

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
  const { colors } = useTheme();
  const pull = usePullRefresh(() => tools.refresh?.());
  const tools = useTools(id);
  const { rows, groups, cats } = groupTools(tools.data?.tools);
  const pending = tools.loading && rows.length === 0;
  const bones = useSkeleton(pending);
  const revealed = useReveal(bones);

  return (
    <>
      <ScrollView refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />} contentContainerStyle={{ paddingBottom: space.s9 }}>
        {bones ? (
          <ListSkeleton rows={4} helper="sm" label="Loading tools" style={{ marginTop: space.s5 }} />
        ) : pending ? null : <FadeIn animate={revealed}>{tools.error && rows.length === 0 ? (
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
                    <PanelRow
                      title={t.name}
                      sub={firstSentence(t.description) || null}
                      meta={t.denied ? 'denied' : null}
                      off={!!t.denied}
                      selected={t.name === selectedName}
                      onPress={() => onOpen(t)}
                    />
                  </View>
                ))}
              </RowGroup>
            </View>
          ))
        )}</FadeIn>}
      </ScrollView>
    </>
  );
}
