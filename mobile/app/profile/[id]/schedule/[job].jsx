import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Alert, Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { lineHeights, space } from '../../../../src/theme/tokens';

import { ActionSheet } from '../../../../src/components/ActionSheet';
import { LoadFailed } from '../../../../src/components/LoadFailed';
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
import { describeTimeout, describeWhen, rawWhen } from '../../../../../common/schedule.mjs';
import { useTheme } from '../../../../src/theme/ThemeContext';

function Fact({ label, children, tone }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ flexDirection: 'row', gap: space.s5, minHeight: 24, alignItems: 'baseline' }}>
      <Text style={{ width: 72, fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{label}</Text>
      <Text style={{ flex: 1, fontFamily: fonts.mono, fontSize: fontSizes.sm, color: tone === 'danger' ? colors.dangerText : colors.ink }}>{children}</Text>
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
  const pull = usePullRefresh(() => schedule.refresh?.());
  const [busy, setBusy] = useState(false);
  const [more, setMore] = useState(false);
  const job = (schedule.data?.jobs ?? []).find((j) => String(j.id) === String(jobId)) ?? null;

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
      ) : !job ? (
        <View style={{ padding: space.s10, alignItems: 'center' }}>
          {schedule.loading ? <ActivityIndicator color={colors.ink3} /> : (
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3 }}>This job is gone.</Text>
          )}
        </View>
      ) : (
        <ScrollView
          refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />}
          contentContainerStyle={{ padding: space.s8, gap: space.s6, paddingBottom: space.s10 }}
        >
          <View style={{ gap: space.s3 }}>
            <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xl, color: colors.ink }}>{jobTitle(job)}</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4, flexWrap: 'wrap' }}>
              <StatusWord word={job.paused ? 'paused' : 'active'} on={!job.paused} />
              <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink2 }}>{describeWhen(job)}</Text>
            </View>
            {failed ? (
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.dangerText }}>{formatLastRun(job.last_run_at, job.last_run_status)}</Text>
            ) : null}
          </View>
          <View style={{ flexDirection: 'row', gap: space.s3 }}>
            <View style={{ flex: 1 }}>
              <Button title="Run now" variant="primary" fullWidth disabled={busy} onPress={() => act('host.schedule.fire', {}, `Fired ${jobTitle(job)}`)} />
            </View>
            <View style={{ flex: 1 }}>
              <Button title={job.paused ? 'Resume' : 'Pause'} variant="secondary" fullWidth disabled={busy} onPress={() => act('host.schedule.set_paused', { paused: !job.paused })} />
            </View>
          </View>
          <View style={{ gap: space.s2 }}>
            {rawWhen(job) ? <Fact label={job.kind}>{rawWhen(job)}</Fact> : null}
            {next ? <Fact label="next">{next}</Fact> : null}
            <Fact label="last run" tone={failed ? 'danger' : undefined}>{formatLastRun(job.last_run_at, job.last_run_status)}</Fact>
            <Fact label="runs">{[job.no_agent ? 'shell script' : 'agent', describeTimeout(job)].filter(Boolean).join(' · ')}</Fact>
            {job.timeout_error ? <Fact label="timeout" tone="danger">{job.timeout_error}</Fact> : null}
            <Fact label="notify">{job.notify ? 'pushes to your apps' : 'silent — failures still alert'}</Fact>
            <Fact label="id">{String(job.id)}</Fact>
          </View>
          {job.prompt ? (
            job.no_agent ? (
              <Text selectable style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.cozy, color: colors.ink }}>{job.prompt}</Text>
            ) : (
              <RichText size={fontSizes.md} color={colors.ink}>{job.prompt}</RichText>
            )
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
