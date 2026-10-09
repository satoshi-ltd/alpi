import { Pressable, Text, View } from 'react-native';
import { mobile, space } from '../../theme/tokens';

import { Eyebrow } from '../../components/Eyebrow';
import { Icon } from '../../components/Icon';
import { useProfileSummaries } from '../../hooks/useDaemonData';
import { useTheme } from '../../theme/ThemeContext';
import { ActivityRow, activitySections } from '../shell/ActivityList';

export const BAND_MAX = 3;

export function bandOf(activity, nowSec = Date.now() / 1000) {
  const needs = activitySections(activity, nowSec).find((section) => section.key === 'needs');
  return needs ? { total: needs.rows.length, rows: needs.rows.slice(0, BAND_MAX) } : null;
}

export function NeedsYouBand({ activity, onOpen, onRun, onOpenActivity, nowSec }) {
  const { colors, fonts, fontSizes } = useTheme();
  const summaries = useProfileSummaries();
  const band = activity ? bandOf(activity, nowSec) : null;
  if (!band) return null;
  const byName = Object.fromEntries((summaries.data?.profiles ?? []).map((p) => [p.name, p]));
  return (
    <View accessibilityRole="list" style={{ backgroundColor: colors.hover, borderBottomWidth: 0.5, borderBottomColor: colors.line }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingLeft: space.s7, paddingTop: space.s3 }}>
        <Eyebrow color={colors.warningText ?? colors.warning} style={{ flex: 1 }}>{`Needs you · ${band.total}`}</Eyebrow>
        {onOpenActivity ? (
          <Pressable
            onPress={onOpenActivity}
            accessibilityRole="button"
            accessibilityLabel={`Activity, ${band.total} waiting`}
            style={{ minHeight: mobile.tap, flexDirection: 'row', alignItems: 'center', gap: space.s1, paddingHorizontal: space.s7, marginTop: -space.s3 }}
          >
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>Activity</Text>
            <Icon name="chevron-right" size="xs" color={colors.ink4} />
          </Pressable>
        ) : null}
      </View>
      {band.rows.map((row) => <ActivityRow key={row.key} row={row} onPress={onOpen} onRun={onRun} who={byName[row.profile]} />)}
    </View>
  );
}
