import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { lineHeights, mobile, radii, space } from '../../theme/tokens';

import { ActionSheet } from '../../components/ActionSheet';
import { AlertBanner } from '../../components/AlertBanner';
import { Busy } from '../../components/Busy';
import { Button } from '../../components/Button';
import { Icon } from '../../components/Icon';
import { LoadFailed } from '../../components/LoadFailed';
import { RichText } from '../../components/RichText';
import { useToast } from '../../components/Toast';
import { Bold, TypedConfirm } from '../../components/TypedConfirm';
import { useAttention } from '../../hooks/useAttention';
import { useBusyVisible } from '../../hooks/useBusyVisible';
import { useScheduleList } from '../../hooks/useDaemonData';
import { useEventEffect } from '../../hooks/useEvents';
import { useOutputs } from '../../hooks/useOutputs';
import { usePullRefresh } from '../../hooks/usePullRefresh';
import { copyText } from '../../lib/clipboard';
import { useEndpoint } from '../../lib/EndpointContext';
import { clockOf, formatLastRun, formatNextFire, jobFailed, jobTitle } from '../../lib/scheduleFormat';
import { useTheme } from '../../theme/ThemeContext';
import { jobBanner, jobItem, nextRunWord } from '../../../../common/attention.mjs';
import { describeTimeout, describeWhen, rawWhen } from '../../../../common/schedule.mjs';
import { PanelHeader } from '../profile/PanelHeader';
import { StatusWord } from '../profile/StatusWord';
import { changeDraft, chatWithDraft } from './drafts';
import { useRunningJob } from './useRunningJob';

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

export function statusOf(job, running) {
  if (running) return { word: 'running', on: true, danger: false };
  if (job.paused) return { word: 'paused', on: false, danger: false };
  if (jobFailed(job)) return { word: 'failed', on: false, danger: true };
  return { word: 'active', on: true, danger: false };
}

export function confirmWord(job) {
  const title = jobTitle(job);
  return title.length <= 32 ? title : String(job.id);
}

export function JobDetail({ profile, jobId, embedded = false, onBack, onGone }) {
  const router = useRouter();
  const toast = useToast();
  const { colors, fonts, fontSizes } = useTheme();
  const schedule = useScheduleList(profile);
  const { att } = useAttention(profile);
  const outputs = useOutputs({ profile });
  const pull = usePullRefresh(() => schedule.refresh?.());
  const [busy, setBusy] = useState(false);
  const [more, setMore] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const job = (schedule.data?.jobs ?? []).find((j) => String(j.id) === String(jobId)) ?? null;
  const opening = !job && schedule.loading;
  const holding = useBusyVisible(opening);
  const run = useRunningJob(profile, job);
  const jobRef = useRef(job);
  jobRef.current = job;
  const { call } = useEndpoint();

  const lastOutput = job ? (outputs.rows ?? []).find((row) => String(row.job_id) === String(job.id)) ?? null : null;
  const openOutput = (outputProfile, outputId) => router.push(`/outputs/${outputProfile}/${outputId}`);

  useEventEffect(['schedule.done', 'schedule.failed', 'schedule.changed'], (ev) => {
    if (ev.data?.profile !== profile) return;
    schedule.refresh();
    const mine = jobRef.current && String(ev.data?.job_id) === String(jobRef.current.id);
    if (!mine || (ev.event !== 'schedule.done' && ev.event !== 'schedule.failed')) return;
    const wasRunning = run.wasRunning();
    run.finished();
    if (ev.event === 'schedule.done' && wasRunning) {
      const outputId = ev.data?.output_id;
      toast({
        message: `${jobTitle(jobRef.current)} finished`,
        kind: 'success',
        duration: 6000,
        ...(outputId ? { action: 'View', onAction: () => openOutput(profile, outputId) } : {}),
      });
    }
  });

  const act = async (method, params, onDone) => {
    setBusy(true);
    try {
      await call(method, { profile, id: job.id, ...params });
      onDone?.();
      schedule.refresh();
    } catch (e) {
      run.finished();
      toast({ message: String(e?.message ?? e), kind: 'danger', duration: 4000 });
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setConfirming(false);
    try {
      await call('host.schedule.remove', { profile, id: job.id });
      schedule.refresh();
      onGone?.();
    } catch (e) {
      toast({ message: String(e?.message ?? e), kind: 'danger', duration: 4000 });
    }
  };

  const failed = jobFailed(job);
  const status = job ? statusOf(job, run.running) : null;
  const about = typeof job?.description === 'string' ? job.description.trim() : '';
  const flagged = job ? jobItem(att, job.id) : null;
  const banner = failed
    ? jobBanner(
        flagged ?? { message: job.last_run_message, last_ok_at: job.last_ok_at },
        formatNextFire((flagged ?? job).last_ok_at) ?? '',
      )
    : null;
  const next = job && !job.paused ? formatNextFire(job.next_fire) : null;
  const moreButton = job ? (
    <Pressable accessibilityRole="button" accessibilityLabel="More" onPress={() => setMore(true)} style={{ width: mobile.tap, height: mobile.tap, alignItems: 'center', justifyContent: 'center' }}>
      <Icon name="ellipsis" size="lg" color={colors.ink2} />
    </Pressable>
  ) : null;

  const actions = job ? [
    ...(lastOutput ? [{ id: 'output', label: 'Last output', detail: 'opens the notification', icon: <Icon name="file-text" size="lg" color={colors.ink2} />, onPress: () => { setMore(false); openOutput(lastOutput.profile ?? profile, lastOutput.id); } }] : []),
    { id: 'copy', label: 'Copy job id', detail: String(job.id), icon: <Icon name="copy" size="lg" color={colors.ink2} />, onPress: async () => { setMore(false); if (await copyText(job.id)) toast({ message: 'Copied', kind: 'success', duration: 1500 }); } },
    // iOS drops a modal presented while the ActionSheet is still dismissing (~220ms).
    { id: 'delete', label: 'Delete job…', danger: true, icon: <Icon name="trash" size="lg" color={colors.danger} />, onPress: () => { setMore(false); setTimeout(() => setConfirming(true), 350); } },
  ] : [];

  return (
    <View style={{ flex: 1 }}>
      {embedded ? null : <PanelHeader profile={profile} section="SCHEDULES" onBack={onBack} right={moreButton} />}
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
          {failed && !run.running ? <AlertBanner {...banner} /> : null}
          <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: space.s3 }}>
            <View style={{ flex: 1, gap: space.s3 }}>
              <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xl, color: colors.ink }}>{jobTitle(job)}</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4, flexWrap: 'wrap' }}>
                <StatusWord word={status.word} on={status.on} danger={status.danger} />
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{describeWhen(job)}</Text>
              </View>
            </View>
            {embedded ? moreButton : null}
          </View>
          <View style={{ flexDirection: 'row', gap: space.s3 }}>
            <View style={{ flex: 1 }}>
              <Button
                title={run.running ? `Running · ${run.elapsed ?? '0:00'}` : 'Run now'}
                variant="primary"
                fullWidth
                disabled={busy || run.running}
                onPress={() => act('host.schedule.fire', {}, run.started)}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Button title={job.paused ? 'Resume' : 'Pause'} variant="secondary" fullWidth disabled={busy || run.running} onPress={() => act('host.schedule.set_paused', { paused: !job.paused })} />
            </View>
          </View>
          <Pressable
            onPress={() => router.push(chatWithDraft(profile, changeDraft(job)))}
            accessibilityRole="button"
            accessibilityLabel="Ask the agent to change this"
            style={({ pressed }) => ({
              minHeight: mobile.tap,
              flexDirection: 'row',
              alignItems: 'center',
              justifyContent: 'center',
              gap: space.s3,
              borderRadius: radii.xs,
              borderWidth: 0.5,
              borderColor: colors.line2,
              backgroundColor: pressed ? colors.selected : 'transparent',
            })}
          >
            <Icon name="sparkle" size="sm" color={colors.ink2} />
            <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.ink2 }}>Ask the agent to change this</Text>
          </Pressable>
          <View style={{ gap: space.s4 }}>
            {about ? <Fact label="ABOUT"><FactText>{about}</FactText></Fact> : null}
            <Fact label="WHEN">
              <FactText>{describeWhen(job)}</FactText>
              {rawWhen(job) ? <Chip>{rawWhen(job)}</Chip> : null}
            </Fact>
            {next ? <Fact label="NEXT"><FactText>{[next, nextRunWord(job)].filter(Boolean).join(' · ')}</FactText></Fact> : null}
            <Fact label="LAST RUN">
              <FactText tone={failed && !run.running ? 'danger' : undefined}>
                {run.running ? `running since ${run.startedMs ? clockOf(run.startedMs / 1000) : 'now'}` : formatLastRun(job.last_run_at, job.last_run_status)}
              </FactText>
            </Fact>
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
      <ActionSheet open={more} onClose={() => setMore(false)} title={job ? jobTitle(job) : ''} actions={actions} />
      {job ? (
        <TypedConfirm
          open={confirming}
          onClose={() => setConfirming(false)}
          title={`Delete “${jobTitle(job)}”`}
          body={<>The job stops firing and is removed. The agent can recreate it later from chat. <Bold>This cannot be undone.</Bold></>}
          expected={confirmWord(job)}
          confirmLabel="Delete job"
          onConfirm={remove}
        />
      ) : null}
    </View>
  );
}
