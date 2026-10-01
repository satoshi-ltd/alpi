import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';

import { ICON_ROLES } from '../../../../common/iconRoles.mjs';
import { Eyebrow } from '../../components/Eyebrow';
import { Icon } from '../../components/Icon';
import { recentlyFailed, toEpochSeconds } from '../../hooks/useActivity';
import { mobile, lineHeights, radii, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';
import { EMPTY } from '../../../../common/emptyCopy.mjs';

function span(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86400)}d`;
}

export function ago(at, nowSec) {
  const sec = toEpochSeconds(at);
  return sec === null ? '' : `${span(nowSec - sec)} ago`;
}

export function until(at, nowSec) {
  const sec = toEpochSeconds(at);
  if (sec === null) return '';
  return sec <= nowSec ? 'due now' : `in ${span(sec - nowSec)}`;
}

function needsYouRow(item, nowSec) {
  const question = item.kind === 'clarification';
  return {
    key: `need:${item.request_id}`,
    tone: 'warning',
    icon: 'triangle-alert',
    title: [item.profile, item.title || (question ? 'a question' : 'a command')].filter(Boolean).join(' · '),
    sub: [question ? 'question' : 'approval', ago(item.ts, nowSec)].filter(Boolean).join(' · '),
    action: 'Review',
    target: { type: 'request', domain: question ? 'clarification' : 'approval', requestId: item.request_id },
  };
}

function runningRow(run, nowSec) {
  if (run.kind === 'workgroup') {
    const total = Number(run.phases_total);
    const phase = Number.isFinite(total) && total > 0 ? `phase ${Number(run.phases_done) || 0} of ${total}` : 'running';
    return {
      key: `wg:${run.workgroup_id}`,
      tone: 'accent',
      icon: ICON_ROLES.activity,
      title: [run.name || run.workgroup_id, run.phase ? `#${run.phase}` : null].filter(Boolean).join(' · '),
      sub: [phase, run.pipeline].filter(Boolean).join(' · '),
      target: { type: 'path', path: `/wg/${run.workgroup_id}` },
    };
  }
  const sid = run.session_id ? `?sid=${encodeURIComponent(run.session_id)}` : '';
  return {
    key: `turn:${run.profile}:${run.session_id ?? ''}`,
    tone: 'accent',
    icon: ICON_ROLES.activity,
    title: [run.profile, run.title || 'working'].filter(Boolean).join(' · '),
    sub: [run.started_at ? span(nowSec - toEpochSeconds(run.started_at)) : null, run.source].filter(Boolean).join(' · '),
    target: run.profile ? { type: 'path', path: `/chat/${run.profile}${sid}` } : null,
  };
}

function scheduledRow(job, nowSec) {
  const failed = recentlyFailed(job, nowSec);
  return {
    key: `job:${job.profile}:${job.job_id}`,
    tone: failed ? 'danger' : 'quiet',
    icon: failed ? 'x' : 'clock',
    title: [job.profile, job.title || job.job_id].filter(Boolean).join(' · '),
    sub: failed ? `failed ${ago(job.last_run_at, nowSec)}`.trim() : until(job.next_fire, nowSec) || 'not scheduled',
    target: job.profile ? { type: 'path', path: `/profile/${job.profile}/schedule` } : null,
  };
}

export function activitySections(activity, nowSec = Date.now() / 1000) {
  const sections = [];
  if (activity.needsYou.length) {
    sections.push({ key: 'needs', label: `Needs you · ${activity.needsYou.length}`, rows: activity.needsYou.map((i) => needsYouRow(i, nowSec)) });
  }
  if (activity.running.length) {
    sections.push({ key: 'running', label: `Running · ${activity.running.length}`, rows: activity.running.map((r) => runningRow(r, nowSec)) });
  }
  if (activity.scheduled.length) {
    sections.push({ key: 'scheduled', label: 'Scheduled', rows: activity.scheduled.map((j) => scheduledRow(j, nowSec)) });
  }
  return sections;
}

export function activityTint(tone, colors) {
  return {
    warning: colors.warningText ?? colors.warning,
    accent: colors.accent,
    danger: colors.dangerText ?? colors.danger,
    quiet: colors.ink3,
  }[tone];
}

function ActivityRow({ row, onPress }) {
  const { colors, fonts, fontSizes } = useTheme();
  const tint = activityTint(row.tone, colors);
  return (
    <Pressable
      onPress={row.target ? () => onPress(row.target) : undefined}
      disabled={!row.target}
      accessibilityRole="button"
      accessibilityLabel={[row.title, row.sub, row.action].filter(Boolean).join(', ')}
      style={({ pressed }) => ({
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s5,
        minHeight: mobile.tap + space.s5,
        paddingHorizontal: space.s7,
        paddingVertical: space.s3,
        backgroundColor: pressed ? colors.selected : 'transparent',
      })}
    >
      <Icon name={row.icon} size="md" color={tint} />
      <View style={{ flex: 1, minWidth: 0, gap: space.s1 }}>
        <Text numberOfLines={2} style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.lg, lineHeight: fontSizes.lg * lineHeights.cozy, color: colors.ink }}>
          {row.title}
        </Text>
        {row.sub ? (
          <Text numberOfLines={1} style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.cozy, color: row.tone === 'danger' ? tint : colors.ink3 }}>
            {row.sub}
          </Text>
        ) : null}
      </View>
      {row.action ? (
        <View style={{ paddingHorizontal: space.s5, paddingVertical: space.s2, borderRadius: radii.lg, backgroundColor: colors.ink }}>
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.sm, color: colors.bgPane }}>{row.action}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

function Empty({ unsupported }) {
  const { colors, fonts, fontSizes } = useTheme();
  const [title, body] = !unsupported
    ? [EMPTY.activity.title, EMPTY.activity.hint]
    : ['Activity needs a newer daemon', 'Update alpi on this connection to see what is running and what waits on you.'];
  return (
    <View style={{ alignItems: 'center', padding: space.s8, gap: space.s3, marginTop: space.s11 }}>
      <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink2, textAlign: 'center' }}>{title}</Text>
      <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3, textAlign: 'center' }}>{body}</Text>
    </View>
  );
}

export function ActivityList({ activity, supported, unsupported = false, onOpen, refreshing = false, onRefresh, nowSec }) {
  const { colors } = useTheme();
  const sections = supported ? activitySections(activity, nowSec) : [];
  const settled = supported || unsupported;
  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={{ paddingBottom: space.s9 }}
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink3} /> : undefined}
    >
      {settled && sections.length === 0 ? <Empty unsupported={unsupported} /> : null}
      {sections.map((section) => (
        <View key={section.key} accessibilityRole="list">
          <View style={{ paddingHorizontal: space.s7, paddingTop: space.s7, paddingBottom: space.s2 }}>
            <Eyebrow color={section.key === 'needs' ? colors.warningText ?? colors.warning : undefined}>{section.label}</Eyebrow>
          </View>
          {section.rows.map((row) => <ActivityRow key={row.key} row={row} onPress={onOpen} />)}
        </View>
      ))}
    </ScrollView>
  );
}
