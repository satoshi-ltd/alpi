import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';

import { WORKGROUP_FOLD } from '../../../../common/folds.mjs';
import { ICON_ROLES } from '../../../../common/iconRoles.mjs';
import { Eyebrow } from '../../components/Eyebrow';
import { Fold } from '../../components/Fold';
import { Icon } from '../../components/Icon';
import { useProfileSummaries } from '../../hooks/useDaemonData';
import { recentlyFailed, toEpochSeconds } from '../../hooks/useActivity';
import { profileLabel } from '../../lib/profileName';
import { clockOf, dayLabel } from '../../lib/scheduleFormat';
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
    profile: item.profile,
    icon: 'triangle-alert',
    title: [profileLabel(item.profile), item.title || (question ? 'a question' : 'a command')].filter(Boolean).join(' · '),
    sub: [question ? 'question' : 'approval', ago(item.ts, nowSec)].filter(Boolean).join(' · '),
    action: 'Review',
    target: { type: 'request', domain: question ? 'clarification' : 'approval', requestId: item.request_id },
  };
}

export const NEXT_UP_CAP = 20;
const NO_FIXED_TIME = 'No fixed time';

function jobTarget(profile, jobId) {
  if (!profile) return null;
  const tail = jobId ? `/${encodeURIComponent(jobId)}` : '';
  return { type: 'path', path: `/profile/${profile}/schedule${tail}` };
}

function runningRow(run, nowSec) {
  if (run.kind === 'workgroup') {
    const total = Number(run.phases_total);
    const phase = Number.isFinite(total) && total > 0 ? `phase ${Number(run.phases_done) || 0} of ${total}` : 'running';
    return {
      key: `wg:${run.workgroup_id}`,
      tone: 'accent',
      profile: run.profile,
      workgroup: true,
      icon: ICON_ROLES.activity,
      title: [run.name || run.workgroup_id, run.phase ? `#${run.phase}` : null].filter(Boolean).join(' · '),
      sub: [phase, run.pipeline].filter(Boolean).join(' · '),
      target: { type: 'path', path: `/wg/${run.workgroup_id}` },
    };
  }
  const sid = run.session_id ? `?sid=${encodeURIComponent(run.session_id)}` : '';
  const target = run.job_id ? jobTarget(run.profile, run.job_id) : run.profile ? { type: 'path', path: `/chat/${run.profile}${sid}` } : null;
  return {
    key: run.job_id ? `run:${run.profile}:${run.job_id}` : `turn:${run.profile}:${run.session_id ?? ''}`,
    tone: 'accent',
    profile: run.profile,
    icon: ICON_ROLES.activity,
    title: [profileLabel(run.profile), run.title || 'working'].filter(Boolean).join(' · '),
    sub: [run.started_at ? span(nowSec - toEpochSeconds(run.started_at)) : null, run.job_id ? 'scheduled' : run.source].filter(Boolean).join(' · '),
    target,
  };
}

function failedJobRow(job, nowSec) {
  return {
    key: `fail:${job.profile}:${job.job_id}`,
    tone: 'danger',
    profile: job.profile,
    icon: 'x',
    title: [profileLabel(job.profile), job.title || job.job_id].filter(Boolean).join(' · '),
    sub: `failed ${ago(job.last_run_at, nowSec)}`.trim(),
    action: 'Run again',
    run: { profile: job.profile, jobId: job.job_id },
    target: jobTarget(job.profile, job.job_id),
  };
}

function nextRow(job, nowSec) {
  const at = toEpochSeconds(job.next_fire);
  return {
    key: `job:${job.profile}:${job.job_id}`,
    tone: 'quiet',
    profile: job.profile,
    icon: 'clock',
    title: [profileLabel(job.profile), job.title || job.job_id].filter(Boolean).join(' · '),
    sub: until(job.next_fire, nowSec) || 'not scheduled',
    when: at === null ? '' : clockOf(at),
    at,
    target: jobTarget(job.profile, job.job_id),
  };
}

function nextGroups(scheduled, nowSec) {
  const rows = scheduled.map((job) => nextRow(job, nowSec));
  const dated = rows.filter((row) => row.at !== null).sort((a, b) => a.at - b.at);
  const groups = [];
  for (const row of dated) {
    const label = dayLabel(row.at, nowSec);
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.rows.push(row);
    else groups.push({ label, rows: [row] });
  }
  const undated = rows.filter((row) => row.at === null);
  if (undated.length) groups.push({ label: NO_FIXED_TIME, rows: undated });
  return groups;
}

export function activitySections(activity, nowSec = Date.now() / 1000) {
  const sections = [];
  const rerunning = new Set(activity.running.filter((run) => run.job_id).map((run) => `${run.profile}/${run.job_id}`));
  const needs = [
    ...activity.needsYou.map((item) => needsYouRow(item, nowSec)),
    ...activity.scheduled
      .filter((job) => recentlyFailed(job, nowSec) && !rerunning.has(`${job.profile}/${job.job_id}`))
      .map((job) => failedJobRow(job, nowSec)),
  ];
  if (needs.length) {
    sections.push({ key: 'needs', label: `Needs you · ${needs.length}`, rows: needs });
  }
  if (activity.running.length) {
    sections.push({ key: 'running', label: `Running · ${activity.running.length}`, rows: activity.running.map((r) => runningRow(r, nowSec)) });
  }
  if (activity.scheduled.length) {
    const groups = nextGroups(activity.scheduled, nowSec);
    const count = activity.scheduled.length;
    sections.push({ key: 'next', label: count >= NEXT_UP_CAP ? `Next up · ${count} shown` : `Next up · ${count}`, groups });
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

export function ActivityRow({ row, onPress, onRun, who }) {
  const { colors, fonts, fontSizes } = useTheme();
  const tint = activityTint(row.tone, colors);
  const lead = who || row.workgroup
    ? <Fold fold={row.workgroup ? WORKGROUP_FOLD : who?.fold} color={who?.accent ?? undefined} size="md" pulse={row.tone === 'accent'} />
    : <Icon name={row.icon} size="lg" color={tint} />;
  const separate = !!row.run && !!onRun;
  const chip = (
    <View style={{ paddingHorizontal: space.s5, paddingVertical: space.s2, borderRadius: radii.xs, backgroundColor: colors.ink }}>
      <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.sm, color: colors.bgPane }}>{row.action}</Text>
    </View>
  );
  const main = (
    <Pressable
      onPress={row.target ? () => onPress(row.target) : undefined}
      disabled={!row.target}
      accessibilityRole="button"
      accessibilityLabel={[row.title, row.sub, separate ? null : row.action].filter(Boolean).join(', ')}
      style={({ pressed }) => ({
        flex: 1,
        minWidth: 0,
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s5,
        minHeight: mobile.tap + space.s5,
        paddingLeft: space.s7,
        paddingRight: separate ? space.s3 : space.s7,
        paddingVertical: space.s3,
        backgroundColor: pressed ? colors.selected : 'transparent',
      })}
    >
      {lead}
      <View style={{ flex: 1, minWidth: 0, gap: space.s1 }}>
        <Text numberOfLines={2} style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.lg, lineHeight: fontSizes.lg * lineHeights.cozy, color: colors.ink }}>
          {row.title}
        </Text>
        {row.sub ? (
          <Text numberOfLines={1} style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.cozy, color: row.tone === 'danger' || row.tone === 'warning' ? tint : colors.ink3 }}>
            {row.sub}
          </Text>
        ) : null}
      </View>
      {row.when ? (
        <Text style={{ fontFamily: fonts.monoMedium ?? fonts.mono, fontSize: fontSizes.md, color: colors.ink2 }}>{row.when}</Text>
      ) : null}
      {row.action && !separate ? chip : null}
    </Pressable>
  );
  if (!separate) return main;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      {main}
      <Pressable
        onPress={() => onRun(row.run)}
        accessibilityRole="button"
        accessibilityLabel={`${row.action} ${row.title}`}
        style={{ minHeight: mobile.tap, minWidth: mobile.tap, paddingRight: space.s7, paddingLeft: space.s3, alignItems: 'center', justifyContent: 'center' }}
      >
        {chip}
      </Pressable>
    </View>
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

export function ActivityList({ activity, supported, unsupported = false, onOpen, onRun, refreshing = false, onRefresh, nowSec }) {
  const { colors } = useTheme();
  const summaries = useProfileSummaries();
  const byName = Object.fromEntries((summaries.data?.profiles ?? []).map((p) => [p.name, p]));
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
          {(section.groups ?? [{ rows: section.rows }]).map((group) => (
            <View key={group.label ?? 'rows'}>
              {group.label ? (
                <View style={{ paddingHorizontal: space.s7, paddingTop: space.s5, paddingBottom: space.s1 }}>
                  <Eyebrow>{group.label}</Eyebrow>
                </View>
              ) : null}
              {group.rows.map((row) => <ActivityRow key={row.key} row={row} onPress={onOpen} onRun={onRun} who={byName[row.profile]} />)}
            </View>
          ))}
        </View>
      ))}
    </ScrollView>
  );
}
