import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { mobile, space } from '../../theme/tokens';

import { Button } from '../../components/Button';
import { Dot } from '../../components/Dot';
import { Field } from '../../components/Field';
import { ListSkeleton } from '../../components/ListSkeleton';
import { LoadFailed } from '../../components/LoadFailed';
import { Row, RowGroup, RowSeparator, SectionHeader } from '../../components/Row';
import { toEpochSeconds, useActivity } from '../../hooks/useActivity';
import { useScheduleList } from '../../hooks/useDaemonData';
import { useEventEffect } from '../../hooks/useEvents';
import { usePullRefresh } from '../../hooks/usePullRefresh';
import { clockOf, jobMatches, jobTitle, lastResultLine } from '../../lib/scheduleFormat';
import { useTheme } from '../../theme/ThemeContext';
import { EMPTY } from '../../../../common/emptyCopy.mjs';
import { jobGroups, nextRunWord } from '../../../../common/attention.mjs';
import { describeWhen } from '../../../../common/schedule.mjs';
import { NEW_SCHEDULE_DRAFT, chatWithDraft } from './drafts';

function JobRow({ job, running, startedClock, selected, onOpen }) {
  const { colors, fonts, fontSizes } = useTheme();
  const paused = !!job.paused;
  const failed = !paused && job.last_run_status === 'error' && !running;
  const word = running ? 'running' : nextRunWord(job);
  const description = typeof job.description === 'string' ? job.description.trim() : '';
  const last = lastResultLine(job, running ? startedClock : null);
  return (
    <Pressable
      onPress={() => onOpen(job.id)}
      accessibilityRole="button"
      accessibilityLabel={`${jobTitle(job)}, ${describeWhen(job)}${running ? ', running' : paused ? ', paused' : failed ? ', last run failed' : ''}`}
      android_ripple={{ color: colors.selected }}
      style={({ pressed }) => ({
        minHeight: mobile.tap,
        paddingHorizontal: space.s8,
        paddingVertical: space.s5,
        gap: space.s1,
        justifyContent: 'center',
        backgroundColor: selected || pressed ? colors.selected : 'transparent',
      })}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4 }}>
        <Dot color={failed ? colors.danger : paused ? colors.ink4 : colors.ink} pulse={running} />
        <Text style={{ flex: 1, fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: paused ? colors.ink3 : colors.ink }} numberOfLines={1}>
          {jobTitle(job)}
        </Text>
        {word ? (
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: failed ? colors.dangerText : colors.ink3 }} numberOfLines={1}>{word}</Text>
        ) : null}
      </View>
      {description ? (
        <Text style={{ marginLeft: space.s6, fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }} numberOfLines={1}>{description}</Text>
      ) : null}
      <Text style={{ marginLeft: space.s6, fontFamily: fonts.mono, fontSize: fontSizes.xs, color: failed ? colors.dangerText : colors.ink3 }} numberOfLines={1}>{last}</Text>
    </Pressable>
  );
}

export function JobList({ profile, selectedId = null, onOpen, embedded = false }) {
  const router = useRouter();
  const { colors } = useTheme();
  const schedule = useScheduleList(profile);
  const { activity } = useActivity();
  const pull = usePullRefresh(() => schedule.refresh?.());
  const [query, setQuery] = useState('');
  const jobs = schedule.data?.jobs ?? [];
  const loadError = schedule.error ? String(schedule.error?.message ?? schedule.error) : null;

  useEventEffect(['schedule.done', 'schedule.failed', 'schedule.changed'], (ev) => {
    if (ev.data?.profile === profile) schedule.refresh();
  });

  const runningRows = useMemo(() => new Map(
    (activity?.running ?? []).filter((run) => run.profile === profile && run.job_id != null).map((run) => [String(run.job_id), run]),
  ), [activity, profile]);
  const startedClock = (job) => {
    const sec = toEpochSeconds(runningRows.get(String(job.id))?.started_at);
    return sec === null ? null : clockOf(sec);
  };
  const shown = jobs.filter((job) => jobMatches(job, query, describeWhen(job)));
  const groups = jobGroups(shown);

  let body;
  if (schedule.loading && jobs.length === 0 && !loadError) {
    body = <ListSkeleton rows={3} title="md" helper="sm" label="Loading schedules" style={{ marginTop: space.s5 }} />;
  } else if (loadError && jobs.length === 0) {
    body = <LoadFailed label="schedule" error={loadError} onRetry={() => schedule.refresh?.()} />;
  } else if (jobs.length === 0) {
    body = (
      <View style={{ gap: space.s6, padding: space.s8 }}>
        <RowGroup>
          <Row label={EMPTY.schedule.title} helper={EMPTY.schedule.hint} chevron={false} />
        </RowGroup>
        <Button title="New schedule" variant="primary" fullWidth onPress={() => router.push(chatWithDraft(profile, NEW_SCHEDULE_DRAFT))} />
      </View>
    );
  } else {
    body = (
      <>
        <View style={{ paddingHorizontal: space.s8, paddingTop: space.s5 }}>
          <Field value={query} onChangeText={setQuery} placeholder="Search jobs…" autoCapitalize="none" autoCorrect={false} />
        </View>
        {shown.length === 0 ? (
          <View style={{ padding: space.s8 }}>
            <RowGroup>
              <Row label={EMPTY.matches.title} helper={EMPTY.matches.hint} chevron={false} />
            </RowGroup>
          </View>
        ) : groups.map((g) => (
          <View key={g.id}>
            <SectionHeader>{`${g.label} · ${g.jobs.length}`}</SectionHeader>
            <RowGroup>
              {g.jobs.map((job, i) => (
                <View key={job.id}>
                  {i > 0 ? <RowSeparator /> : null}
                  <JobRow
                    job={job}
                    running={runningRows.has(String(job.id))}
                    startedClock={startedClock(job)}
                    selected={String(job.id) === String(selectedId)}
                    onOpen={onOpen}
                  />
                </View>
              ))}
            </RowGroup>
          </View>
        ))}
      </>
    );
  }

  return (
    <ScrollView
      style={embedded ? { flex: 1 } : undefined}
      contentContainerStyle={{ paddingBottom: space.s9, flexGrow: 1 }}
      keyboardShouldPersistTaps="handled"
      refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />}
    >
      {body}
    </ScrollView>
  );
}
