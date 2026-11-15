import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { RefreshControl, ScrollView, View } from 'react-native';
import { space } from '../../theme/tokens';
import { PanelRow } from '../../components/PanelRow';

import { Field } from '../../components/Field';
import { ListSkeleton } from '../../components/ListSkeleton';
import { FadeIn } from '../../components/FadeIn';
import { useSkeleton } from '../../hooks/useSkeleton';
import { useReveal } from '../../hooks/useReveal';
import { EmptyState } from '../../components/EmptyState';
import { LoadFailed } from '../../components/LoadFailed';
import { Row, RowGroup, RowSeparator, SectionHeader } from '../../components/Row';
import { useActivity } from '../../hooks/useActivity';
import { useScheduleList } from '../../hooks/useDaemonData';
import { useEventEffect } from '../../hooks/useEvents';
import { usePullRefresh } from '../../hooks/usePullRefresh';
import { jobMatches, jobTitle } from '../../lib/scheduleFormat';
import { useTheme } from '../../theme/ThemeContext';
import { EMPTY } from '../../../../common/emptyCopy.mjs';
import { jobGroups, nextRunWord } from '../../../../common/attention.mjs';
import { describeWhen } from '../../../../common/schedule.mjs';
import { NEW_SCHEDULE_DRAFT, chatWithDraft } from './drafts';

function JobRow({ job, running, selected, onOpen }) {
  const paused = !!job.paused;
  const failed = !paused && job.last_run_status === 'error' && !running;
  const word = running ? 'running' : nextRunWord(job);
  const description = typeof job.description === 'string' ? job.description.trim() : '';
  return (
    <PanelRow
      title={jobTitle(job)}
      sub={description || null}
      meta={word || null}
      metaTone={failed ? 'danger' : null}
      off={paused}
      selected={selected}
      onPress={() => onOpen(job.id)}
      accessibilityLabel={`${jobTitle(job)}, ${describeWhen(job)}${running ? ', running' : paused ? ', paused' : failed ? ', last run failed' : ''}`}
    />
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
  const shown = jobs.filter((job) => jobMatches(job, query, describeWhen(job)));
  const groups = jobGroups(shown);

  const pending = schedule.loading && jobs.length === 0 && !loadError;
  const bones = useSkeleton(pending);
  const revealed = useReveal(bones);
  let body;
  if (bones) {
    body = <ListSkeleton rows={3} title="md" helper="sm" label="Loading schedules" style={{ marginTop: space.s5 }} />;
  } else if (pending) {
    body = null;
  } else if (loadError && jobs.length === 0) {
    body = <LoadFailed label="schedule" error={loadError} onRetry={() => schedule.refresh?.()} />;
  } else if (jobs.length === 0) {
    body = (
      <EmptyState title={EMPTY.schedule.title} detail={EMPTY.schedule.hint} action={{ label: 'New schedule', onPress: () => router.push(chatWithDraft(profile, NEW_SCHEDULE_DRAFT)) }} />
    );
  } else {
    body = (
      <>
        <View style={{ paddingHorizontal: space.s7, paddingTop: space.s5 }}>
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
      {bones || pending ? body : <FadeIn animate={revealed}>{body}</FadeIn>}
    </ScrollView>
  );
}
