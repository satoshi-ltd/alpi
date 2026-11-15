
import { RefreshControl, ScrollView, View } from 'react-native';
import { space } from '../../theme/tokens';

import { useAttention } from '../../hooks/useAttention';
import { skillItem, skillWord } from '../../../../common/attention.mjs';
import { Row, RowGroup, RowSeparator, SectionHeader } from '../../components/Row';
import { PanelRow } from '../../components/PanelRow';
import { skillMeta } from '../../../../common/panelRow.mjs';
import { useSkills } from '../../hooks/useDaemonData';
import { usePullRefresh } from '../../hooks/usePullRefresh';
import { useTheme } from '../../theme/ThemeContext';
import { LoadFailed } from '../../components/LoadFailed';
import { EMPTY } from '../../../../common/emptyCopy.mjs';
import { useSkeleton } from '../../hooks/useSkeleton';
import { useReveal } from '../../hooks/useReveal';
import { FadeIn } from '../../components/FadeIn';
import { ListSkeleton } from '../../components/ListSkeleton';

export function skillKey(s) {
  return s.path ?? `${s.rawCategory ?? s.category ?? ''}/${s.name}`;
}

function formatCategory(raw) {
  if (!raw) return 'Uncategorized';
  return raw.charAt(0).toUpperCase() + raw.slice(1).replace(/-/g, ' ');
}

export function groupSkills(skillList, att) {
  const rows = (skillList ?? []).map((s) => ({
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
  const ordered = [...needs, ...categoryOrder.flatMap((cat) => groups.get(cat))];
  return { rows, needs, groups, categoryOrder, ordered };
}

function SkillRow({ skill, selected, onPress }) {
  const { meta, tone } = skillMeta(skill, skill.flag ? skillWord(skill.flag) : null);
  return <PanelRow title={skill.name} sub={skill.description || null} meta={meta} metaTone={tone} off={!!skill.status && skill.status !== 'active'} selected={selected} onPress={onPress} />;
}

export function SkillsList({ profile: id, selectedKey = null, onOpen }) {
  const { colors } = useTheme();
  const pull = usePullRefresh(() => skills.refresh?.());
  const skills = useSkills(id);
  const { att } = useAttention(id);
  const { rows, needs, groups, categoryOrder } = groupSkills(skills.data?.skills, att);
  const pending = skills.loading && rows.length === 0;
  const bones = useSkeleton(pending);
  const revealed = useReveal(bones);

  return (
    <>
      <ScrollView refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />} contentContainerStyle={{ paddingBottom: space.s9 }}>
        {bones ? (
          <ListSkeleton rows={4} helper="sm" label="Loading skills" style={{ marginTop: space.s5 }} />
        ) : pending ? null : <FadeIn animate={revealed}>{skills.error && rows.length === 0 ? (
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
                    <SkillRow skill={s} selected={skillKey(s) === selectedKey} onPress={() => onOpen(s)} />
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
