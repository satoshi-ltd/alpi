import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { lineHeights, radii, space } from '../../../../src/theme/tokens';

import { ActionSheet } from '../../../../src/components/ActionSheet';
import { LoadFailed } from '../../../../src/components/LoadFailed';
import { AlertBanner } from '../../../../src/components/AlertBanner';
import { useAttention } from '../../../../src/hooks/useAttention';
import { Button } from '../../../../src/components/Button';
import { Icon } from '../../../../src/components/Icon';
import { RichText } from '../../../../src/components/RichText';
import { useToast } from '../../../../src/components/Toast';
import { PanelHeader } from '../../../../src/features/profile/PanelHeader';
import { StatusWord } from '../../../../src/features/profile/StatusWord';
import { useBack } from '../../../../src/hooks/useBack';
import { useScheduleList } from '../../../../src/hooks/useDaemonData';
import { usePullRefresh } from '../../../../src/hooks/usePullRefresh';
import { useEventEffect } from '../../../../src/hooks/useEvents';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { formatLastRun, formatNextFire, jobFailed, jobTitle } from '../../../../src/lib/scheduleFormat';
import { jobBanner, jobItem, nextRunWord } from '../../../../../common/attention.mjs';
import { describeTimeout, describeWhen, rawWhen } from '../../../../../common/schedule.mjs';
import { useTheme } from '../../../../src/theme/ThemeContext';
import { Busy } from '../../../../src/components/Busy';
import { useBusyVisible } from '../../../../src/hooks/useBusyVisible';

function Fact({ label, children }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ flexDirection: 'row', gap: space.s5, minHeight: 24, alignItems: 'baseline' }}>
      <Text style={{ width: 72, fontFamily: fonts.mono, fontSize: fontSizes.xs, letterSpacing: 0.6, color: colors.ink3 }}>{label}</Text>
      <View style={{ flex: 1, gap: space.s2, alignItems: 'flex-start' }}>{children}</View>
    </View>
  );
}

function FactText({ children, tone }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, lineHeight: fontSizes.md * lineHeights.normal, color: tone === 'danger' ? colors.dangerText : colors.ink2 }}>{children}</Text>
  );
}

function Chip({ children }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ paddingHorizontal: space.s3, paddingVertical: 2, borderRadius: radii.xs, backgroundColor: colors.hover }}>
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{children}</Text>
    </View>
  );
}

export default function ScheduleJob() {
  const { id, job: jobId } = useLocalSearchParams();
  const goBack = useBack();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const schedule = useScheduleList(id);
  const { att } = useAttention(id);
  const pull = usePullRefresh(() => schedule.refresh?.());
  const [busy, setBusy] = useState(false);
  const [more, setMore] = useState(false);
  const job = (schedule.data?.jobs ?? []).find((j) => String(j.id) === String(jobId)) ?? null;
  const opening = !job && schedule.loading;
  const holding = useBusyVisible(opening);

  useEventEffect(['schedule.done', 'schedule.failed', 'schedule.changed'], (ev) => {
    if (ev.data?.profile === id) schedule.refresh();
  });

  const act = async (method, params, done) => {
    setBusy(true);
    try {
      await call(method, { profile: id, id: job.id, ...params });
      if (done) toast({ message: done, kind: 'success', duration: 2000 });
      schedule.refresh();
    } catch (e) {
      toast({ message: String(e?.message ?? e), kind: 'danger', duration: 4000 });
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = () => {
    Alert.alert(`Delete "${jobTitle(job)}"?`, 'The job stops firing and is removed. The agent can recreate it later from chat.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await call('host.schedule.remove', { profile: id, id: job.id });
            schedule.refresh();
            goBack();
          } catch (e) {
            toast({ message: String(e?.message ?? e), kind: 'danger', duration: 4000 });
          }
        },
      },
    ]);
  };

  const failed = jobFailed(job);
  const about = typeof job?.description === 'string' ? job.description.trim() : '';
  const flagged = job ? jobItem(att, job.id) : null;
  const banner = failed
    ? jobBanner(
        flagged ?? { message: job.last_run_message, last_ok_at: job.last_ok_at },
        formatNextFire((flagged ?? job).last_ok_at) ?? '',
      )
    : null;
  const next = job && !job.paused ? formatNextFire(job.next_fire) : null;

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <PanelHeader
        profile={id}
        section="SCHEDULES"
        onBack={goBack}
        right={job ? (
          <Pressable accessibilityRole="button" accessibilityLabel="More" onPress={() => setMore(true)} style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="ellipsis" size="lg" color={colors.ink2} />
          </Pressable>
        ) : null}
      />
      {!job && schedule.error && !schedule.data ? (
        <LoadFailed inline label="this job" error={schedule.error} onRetry={() => schedule.refresh?.()} />
      ) : !job || holding ? (
        opening || holding ? <Busy fill visible={holding} label="Opening the job" /> : (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3 }}>This job is gone.</Text>
          </View>
        )
      ) : (
        <ScrollView
          refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />}
          contentContainerStyle={{ padding: space.s8, gap: space.s6, paddingBottom: space.s10 }}
        >
          {failed ? (
            <AlertBanner {...banner} />
          ) : null}
          <View style={{ gap: space.s3 }}>
            <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xl, color: colors.ink }}>{jobTitle(job)}</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4, flexWrap: 'wrap' }}>
              <StatusWord word={job.paused ? 'paused' : 'active'} on={!job.paused} />
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{String(job.id)}</Text>
            </View>
          </View>
          <View style={{ flexDirection: 'row', gap: space.s3 }}>
            <View style={{ flex: 1 }}>
              <Button title="Run now" variant="primary" fullWidth disabled={busy} onPress={() => act('host.schedule.fire', {}, `Fired ${jobTitle(job)}`)} />
            </View>
            <View style={{ flex: 1 }}>
              <Button title={job.paused ? 'Resume' : 'Pause'} variant="secondary" fullWidth disabled={busy} onPress={() => act('host.schedule.set_paused', { paused: !job.paused })} />
            </View>
          </View>
          <View style={{ gap: space.s4 }}>
            {about ? <Fact label="ABOUT"><FactText>{about}</FactText></Fact> : null}
            <Fact label="WHEN">
              <FactText>{describeWhen(job)}</FactText>
              {rawWhen(job) ? <Chip>{rawWhen(job)}</Chip> : null}
            </Fact>
            {next ? <Fact label="NEXT"><FactText>{[next, nextRunWord(job)].filter(Boolean).join(' · ')}</FactText></Fact> : null}
            <Fact label="LAST RUN"><FactText tone={failed ? 'danger' : undefined}>{formatLastRun(job.last_run_at, job.last_run_status)}</FactText></Fact>
            <Fact label="RUNS"><FactText>{[job.no_agent ? 'shell script' : 'agent', describeTimeout(job)].filter(Boolean).join(' · ')}</FactText></Fact>
            {job.timeout_error ? <Fact label="TIMEOUT"><FactText tone="danger">{job.timeout_error}</FactText></Fact> : null}
            <Fact label="NOTIFY"><FactText>{job.notify ? 'pushes to your apps' : 'silent — failures still alert'}</FactText></Fact>
          </View>
          {job.prompt ? (
            <View style={{ padding: space.s5, gap: space.s3, borderRadius: radii.xs, borderWidth: 0.5, borderColor: colors.line, backgroundColor: colors.bg }}>
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, letterSpacing: 0.6, color: colors.ink3 }}>PROMPT</Text>
              {job.no_agent ? (
                <Text selectable style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.cozy, color: colors.ink }}>{job.prompt}</Text>
              ) : (
                <RichText size={fontSizes.md} color={colors.ink2}>{job.prompt}</RichText>
              )}
            </View>
          ) : null}
        </ScrollView>
      )}
      <ActionSheet
        open={more}
        onClose={() => setMore(false)}
        title={job ? jobTitle(job) : ''}
        actions={job ? [
          // iOS drops an Alert presented while the ActionSheet is still dismissing (~220ms).
          { id: 'delete', label: 'Delete', danger: true, icon: <Icon name="trash" size="lg" color={colors.danger} />, onPress: () => { setMore(false); setTimeout(confirmDelete, 350); } },
        ] : []}
      />
    </SafeAreaView>
  );
}
