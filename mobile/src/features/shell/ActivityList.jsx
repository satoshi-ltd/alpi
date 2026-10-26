import { useEffect, useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';

import { WORKGROUP_FOLD } from '../../../../common/folds.mjs';
import { ICON_ROLES } from '../../../../common/iconRoles.mjs';
import { EmptyState } from '../../components/EmptyState';
import { Eyebrow } from '../../components/Eyebrow';
import { Expand } from '../../components/Expand';
import { Fold } from '../../components/Fold';
import { Icon } from '../../components/Icon';
import { useProfileSummaries } from '../../hooks/useDaemonData';
import { recentlyFailed, toEpochSeconds } from '../../hooks/useActivity';
import { profileLabel } from '../../lib/profileName';
import { clockOf, dayLabel } from '../../lib/scheduleFormat';
import { mobile, lineHeights, radii, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';
import { EMPTY } from '../../../../common/emptyCopy.mjs';
import { applyFilter, failingJobs, stripProfilePrefix } from '../../../../common/activityGroups.mjs';
import { pluralize } from '../../../../common/pluralize.mjs';
import {
  ACTIVITY_FILTERS,
  CHIP_H,
  CHIP_ROW_H,
  FILTER_EMPTY,
  FILTER_LABEL,
  GROUP_H,
  JOB_INDENT,
  JOB_ROW_H,
  SECTION_H,
  chipLabel,
  groupLabel,
  retryAllBody,
  toGroups,
} from './activityFeed';

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
    : <Icon name={row.icon} size="md" color={tint} />;
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
  const [title, body] = !unsupported
    ? [EMPTY.activity.title, EMPTY.activity.hint]
    : ['Activity needs a newer daemon', 'Update alpi on this connection to see what is running and what waits on you.'];
  return <EmptyState title={title} detail={body} />;
}

function SectionHeader({ label, tone, right = null }) {
  const { colors } = useTheme();
  const color = tone === 'danger' ? colors.dangerText ?? colors.danger : tone === 'warning' ? colors.warningText ?? colors.warning : undefined;
  return (
    <View
      accessibilityRole="header"
      style={{ minHeight: SECTION_H, flexDirection: 'row', alignItems: 'center', gap: space.s5, paddingHorizontal: space.s7, backgroundColor: colors.bg }}
    >
      <Eyebrow numberOfLines={1} color={color} style={{ flex: 1 }}>{label}</Eyebrow>
      {right}
    </View>
  );
}

function FilterChips({ filter, counts, onChange }) {
  const { colors, fonts, fontSizes, chromeScale } = useTheme();
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel="Filter activity" style={{ backgroundColor: colors.bg, borderBottomWidth: 0.5, borderBottomColor: colors.line }}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: space.s7, gap: space.s3 }}>
        {ACTIVITY_FILTERS.map((id) => {
          const on = filter === id;
          const danger = id === 'failing' && counts[id] > 0;
          return (
            <Pressable
              key={id}
              onPress={() => onChange(id)}
              accessibilityRole="radio"
              accessibilityState={{ selected: on }}
              accessibilityLabel={chipLabel(id, counts[id])}
              style={{ minHeight: CHIP_ROW_H, justifyContent: 'center' }}
            >
              <View
                style={{
                  minHeight: CHIP_H,
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: space.s2,
                  paddingHorizontal: space.s5,
                  borderRadius: radii.xs,
                  backgroundColor: on ? colors.selected : 'transparent',
                  borderWidth: 0.5,
                  borderColor: on ? colors.line2 : colors.line,
                }}
              >
                <Text maxFontSizeMultiplier={chromeScale} numberOfLines={1} style={{ fontFamily: on ? fonts.sans.semibold : fonts.sans.regular, fontSize: fontSizes.sm, color: on ? colors.ink : colors.ink2 }}>
                  {FILTER_LABEL[id]}
                </Text>
                <Text maxFontSizeMultiplier={chromeScale} style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: danger ? colors.dangerText ?? colors.danger : colors.ink3 }}>
                  {counts[id]}
                </Text>
              </View>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

function FailGroupHead({ group, expanded, who, now, onToggle }) {
  const { colors, fonts, fontSizes } = useTheme();
  const name = profileLabel(group.profile);
  const latest = ago(group.latestAt, now);
  return (
    <Pressable
      onPress={onToggle}
      accessibilityRole="button"
      accessibilityState={{ expanded }}
      accessibilityLabel={groupLabel(name, group.count, latest, expanded)}
      style={({ pressed }) => ({
        minHeight: GROUP_H,
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s3,
        paddingHorizontal: space.s7,
        backgroundColor: pressed ? colors.selected : 'transparent',
      })}
    >
      <Icon name={expanded ? 'chevron-down' : 'chevron-right'} size="xs" color={colors.ink3} />
      <Fold fold={who?.fold} color={who?.accent ?? undefined} />
      <Text numberOfLines={1} style={{ flex: 1, minWidth: 0, fontFamily: fonts.sans.medium, fontSize: fontSizes.lg, color: colors.ink }}>{name}</Text>
      <Text numberOfLines={1} style={{ flexShrink: 0, fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>
        {`${group.count} ${pluralize(group.count, 'job')} · `}
        <Text style={{ color: colors.dangerText ?? colors.danger }}>{latest}</Text>
      </Text>
    </Pressable>
  );
}

function FailJobRow({ job, name, now, retryable, busy, onOpen, onRetry }) {
  const { colors, fonts, fontSizes, chromeScale } = useTheme();
  const title = stripProfilePrefix(job.title || job.job_id, name, job.profile);
  const failed = `failed ${ago(job.failedAt, now)}`;
  const lastOk = job.lastOkAt ? `last ok ${ago(job.lastOkAt, now)}` : null;
  const danger = colors.dangerText ?? colors.danger;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      <Pressable
        onPress={() => onOpen(jobTarget(job.profile, job.job_id))}
        accessibilityRole="button"
        accessibilityLabel={[title, failed, lastOk].filter(Boolean).join(', ')}
        accessibilityHint="Opens the job"
        style={({ pressed }) => ({
          flex: 1,
          minWidth: 0,
          minHeight: JOB_ROW_H,
          justifyContent: 'center',
          gap: space.s1,
          paddingLeft: JOB_INDENT,
          paddingRight: retryable ? space.s3 : space.s7,
          paddingVertical: space.s3,
          backgroundColor: pressed ? colors.selected : 'transparent',
        })}
      >
        <Text numberOfLines={1} style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.lg, lineHeight: fontSizes.lg * lineHeights.cozy, color: colors.ink }}>{title}</Text>
        <Text numberOfLines={2} style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.cozy, color: colors.ink3 }}>
          <Text style={{ color: danger }}>{failed}</Text>
          {lastOk ? ` · ${lastOk}` : ''}
        </Text>
      </Pressable>
      {retryable ? (
        <Pressable
          onPress={() => onRetry(job)}
          disabled={busy}
          accessibilityRole="button"
          accessibilityState={{ disabled: busy, busy }}
          accessibilityLabel={`Retry ${title}`}
          style={({ pressed }) => ({
            minHeight: mobile.tap,
            minWidth: mobile.tap,
            marginRight: space.s3,
            paddingHorizontal: space.s5,
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: radii.xs,
            backgroundColor: pressed && !busy ? colors.selected : 'transparent',
          })}
        >
          <Text maxFontSizeMultiplier={chromeScale} style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, color: busy ? colors.ink4 : colors.ink2 }}>Retry</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function Quiet({ children }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ minHeight: GROUP_H, justifyContent: 'center', paddingHorizontal: space.s7 }}>
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.cozy, color: colors.ink3 }}>{children}</Text>
    </View>
  );
}

export function ActivityList({
  activity,
  supported,
  unsupported = false,
  onOpen,
  refreshing = false,
  onRefresh,
  nowSec,
  canRetry = false,
  onRetry = null,
  onRetried = null,
  connectionId = null,
  confirm = null,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const summaries = useProfileSummaries();
  const byName = Object.fromEntries((summaries.data?.profiles ?? []).map((p) => [p.name, p]));
  const [filter, setFilter] = useState('all');
  const [toggled, setToggled] = useState({});
  const [busy, setBusy] = useState(() => new Set());
  const [retryGone, setRetryGone] = useState(false);
  const [tick, setTick] = useState(() => Date.now() / 1000);

  useEffect(() => {
    setRetryGone(false);
  }, [connectionId]);
  useEffect(() => {
    setTick(Date.now() / 1000);
  }, [activity]);
  useEffect(() => {
    if (nowSec != null) return undefined;
    const id = setInterval(() => setTick(Date.now() / 1000), 30000);
    return () => clearInterval(id);
  }, [nowSec]);

  const now = nowSec ?? tick;
  const groups = useMemo(() => (supported ? toGroups(activity, now) : null), [supported, activity, now]);
  const settled = supported || unsupported;
  const retryable = Boolean(canRetry && onRetry && !retryGone);
  const key = (job) => `${job.profile}/${job.job_id}`;
  const target = (job) => ({ profile: job.profile, jobId: job.job_id });

  const mark = (keys, on) => setBusy((prev) => {
    const next = new Set(prev);
    for (const k of keys) (on ? next.add(k) : next.delete(k));
    return next;
  });

  async function retryOne(job) {
    if (busy.has(key(job))) return;
    mark([key(job)], true);
    const { status } = await onRetry(target(job));
    mark([key(job)], false);
    if (status === 'gone') setRetryGone(true);
    else if (status === 'ok') onRetried?.();
  }

  async function retryAll(jobs) {
    const ok = await confirm?.({
      title: `Retry ${jobs.length} ${pluralize(jobs.length, 'job')}?`,
      body: retryAllBody(jobs.length),
      confirmLabel: 'Retry all',
      tone: 'neutral',
      typed: false,
    });
    if (!ok) return;
    const keys = jobs.map(key);
    mark(keys, true);
    let started = 0;
    for (const job of jobs) {
      const { status } = await onRetry(target(job), { quiet: true });
      if (status === 'gone') setRetryGone(true);
      if (status !== 'ok') break;
      started += 1;
    }
    mark(keys, false);
    if (started) onRetried?.(started);
  }

  const children = [];
  const sticky = [];
  const add = (el, header = false) => {
    if (header) sticky.push(children.length);
    children.push(el);
  };

  if (groups) {
    const shown = applyFilter(groups, filter);
    const total = groups.counts.all;
    const failingTotal = shown.failing.reduce((n, g) => n + g.count, 0);
    if (total === 0) {
      add(<Empty key="empty" unsupported={false} />);
    } else if (filter !== 'all' && groups.counts[filter] === 0) {
      add(<Quiet key="filter-empty">{FILTER_EMPTY[filter]}</Quiet>);
    } else if (filter === 'all' && groups.counts.needs === 0 && groups.counts.failing === 0) {
      add(<Quiet key="calm">Nothing needs you now</Quiet>);
    }
    if (shown.needs.length) {
      add(<SectionHeader key="h-needs" label={`Needs you · ${shown.needs.length}`} tone="warning" />, true);
      shown.needs.forEach((item) => {
        const row = needsYouRow(item, now);
        add(<ActivityRow key={row.key} row={row} onPress={onOpen} who={byName[row.profile]} />);
      });
    }
    if (shown.failing.length) {
      const jobs = failingJobs(shown);
      const all = retryable ? (
        <Pressable
          onPress={() => retryAll(jobs)}
          disabled={jobs.some((job) => busy.has(key(job)))}
          accessibilityRole="button"
          accessibilityLabel={`Retry all ${failingTotal} failing ${pluralize(failingTotal, 'job')}`}
          hitSlop={{ top: (mobile.tap - SECTION_H) / 2, bottom: (mobile.tap - SECTION_H) / 2, left: space.s3, right: space.s3 }}
        >
          <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, color: colors.ink2 }}>Retry all</Text>
        </Pressable>
      ) : null;
      add(<SectionHeader key="h-failing" label={`Failing · ${failingTotal}`} tone="danger" right={all} />, true);
      shown.failing.forEach((group, index) => {
        const expanded = toggled[group.profile] ?? index === 0;
        const name = profileLabel(group.profile);
        add(
          <View key={`fail:${group.profile}`}>
            <FailGroupHead group={group} expanded={expanded} who={byName[group.profile]} now={now} onToggle={() => setToggled((prev) => ({ ...prev, [group.profile]: !expanded }))} />
            <Expand open={expanded}>
              {group.jobs.map((job) => (
                <FailJobRow key={key(job)} job={job} name={name} now={now} retryable={retryable} busy={busy.has(key(job))} onOpen={onOpen} onRetry={retryOne} />
              ))}
            </Expand>
          </View>,
        );
      });
    }
    if (shown.running.length) {
      add(<SectionHeader key="h-running" label={`Running · ${shown.running.length}`} />, true);
      shown.running.forEach((run) => {
        const row = runningRow(run, now);
        add(<ActivityRow key={row.key} row={row} onPress={onOpen} who={byName[row.profile]} />);
      });
    }
    if (shown.upcoming.length) {
      const count = shown.upcoming.length;
      add(<SectionHeader key="h-upcoming" label={count >= NEXT_UP_CAP ? `Upcoming · ${count} shown` : `Upcoming · ${count}`} />, true);
      nextGroups(shown.upcoming, now).forEach((day) => {
        add(
          <View key={`day:${day.label}`}>
            <View style={{ paddingHorizontal: space.s7, paddingTop: space.s3, paddingBottom: space.s1 }}>
              <Eyebrow>{day.label}</Eyebrow>
            </View>
            {day.rows.map((row) => <ActivityRow key={row.key} row={row} onPress={onOpen} who={byName[row.profile]} />)}
          </View>,
        );
      });
    }
  } else if (settled) {
    add(<Empty key="unsupported" unsupported={unsupported} />);
  }

  return (
    <View style={{ flex: 1 }}>
      {groups && groups.counts.all > 0 ? <FilterChips filter={filter} counts={groups.counts} onChange={setFilter} /> : null}
      <ScrollView
        style={{ flex: 1 }}
        stickyHeaderIndices={sticky}
        contentContainerStyle={{ paddingBottom: space.s9, flexGrow: 1 }}
        refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink3} /> : undefined}
      >
        {children}
      </ScrollView>
    </View>
  );
}
