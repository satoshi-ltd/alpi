import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space , fontSizes} from '../../../../src/theme/tokens';

import { ActionSheet } from '../../../../src/components/ActionSheet';
import { Icon } from '../../../../src/components/Icon';
import { Row, RowSeparator } from '../../../../src/components/Row';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../../src/components/TypedConfirm';
import { useScheduleList } from '../../../../src/hooks/useDaemonData';
import { useEventEffect } from '../../../../src/hooks/useEvents';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { scheduleSummary } from '../../../../src/lib/scheduleFormat';
import { useTheme } from '../../../../src/theme/ThemeContext';

export default function ScheduleList() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const schedule = useScheduleList(id);
  const [target, setTarget] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const jobs = schedule.data?.jobs ?? [];

  // schedule.changed fires on remove/pause/resume from any client — without it, a desktop pause wouldn't update this screen until manual pull-to-refresh.
  useEventEffect(['schedule.done', 'schedule.failed', 'schedule.changed'], (ev) => {
    if (ev.data?.profile === id) schedule.refresh();
  });

  const fire = async (jid) => {
    setBusyId(jid);
    try {
      await call('host.schedule.fire', { profile: id, id: jid });
      // iOS drops a Modal presented while another is dismissing; defer past the ~220ms ActionSheet close.
      setTimeout(() => toast({ message: `Schedule ${jid} started`, kind: 'success', duration: 2000 }), 350);
    } catch (e) {
      setTimeout(() => toast({ message: `Fire failed: ${String(e)}`, kind: 'danger', duration: 4000 }), 350);
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (jid) => {
    try {
      await call('host.schedule.remove', { profile: id, id: jid });
      toast({ title: 'Deleted', message: jid, duration: 1500 });
      schedule.refresh();
    } catch (e) {
      toast({ title: 'Delete failed', message: String(e) });
    }
  };

  const togglePaused = async (job) => {
    try {
      await call('host.schedule.set_paused', { profile: id, id: job.id, paused: !job.paused });
      schedule.refresh();
    } catch (e) {
      toast({ title: 'Toggle failed', message: String(e) });
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Schedule"
        subtitle={`@${id} · CRON JOBS · ${jobs.length}`}
        onBack={() => router.back()}
        // Schedules are created via chat (ask the agent to set one up) — no in-app "New" affordance. List + manage (fire/pause/delete) live here, creation does not.
      />
      <ScrollView contentContainerStyle={{ paddingBottom: space.s9 }}>
        {schedule.loading && jobs.length === 0 ? (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : jobs.length === 0 ? (
          <Row label="No scheduled jobs" helper="ask the agent to set one up" chevron={false} />
        ) : (
          jobs.map((j, i) => {
            const summary = scheduleSummary(j);
            const desc = j.prompt || '—';
            const paused = !!j.paused;
            return (
              <View key={j.id}>
                {i > 0 ? <RowSeparator /> : null}
                <Pressable
                  onPress={() => setTarget(j)}
                  android_ripple={{ color: colors.selected }}
                  style={({ pressed }) => ({
                    paddingHorizontal: space.s8,
                    paddingVertical: space.s6,
                    gap: space.s1,
                    backgroundColor: pressed ? colors.selected : 'transparent',
                    opacity: paused ? 0.55 : 1,
                  })}
                >
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s5 }}>
                    <Text
                      style={{ flex: 1, fontFamily: fonts.monoMedium, fontSize: fontSizes.md, color: colors.ink }}
                      numberOfLines={1}
                    >
                      {summary}
                    </Text>
                    {busyId === j.id ? (
                      <ActivityIndicator color={colors.ink3} size="small" />
                    ) : (
                      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }} numberOfLines={1}>
                        {j.id}
                      </Text>
                    )}
                  </View>
                  <Text
                    style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3, lineHeight: fontSizes.sm * 1.4 }}
                    numberOfLines={2}
                  >
                    {desc}
                  </Text>
                </Pressable>
              </View>
            );
          })
        )}
      </ScrollView>
      <ActionSheet
        open={!!target}
        onClose={() => setTarget(null)}
        title={target ? scheduleSummary(target) : ''}
        subtitle={target?.id}
        description={target?.prompt ?? null}
        actions={
          target
            ? [
                { id: 'fire', label: 'Fire now', icon: <Icon name="send" size={20} color={colors.ink2} />, onPress: () => fire(target.id) },
                {
                  id: 'toggle',
                  label: target.paused ? 'Resume' : 'Pause',
                  icon: <Icon name="bell" size={20} color={colors.ink2} />,
                  onPress: () => togglePaused(target),
                },
                { divider: true },
                { id: 'delete', label: 'Delete', danger: true, icon: <Icon name="x" size={20} color={colors.danger} />, onPress: () => {
                  const job = target;
                  setTarget(null);
                  setConfirmDelete(job);
                } },
              ]
            : []
        }
      />
      <TypedConfirm
        open={!!confirmDelete}
        onClose={() => setConfirmDelete(null)}
        title="Delete scheduled job"
        body={
          <>
            Removes <Code>{confirmDelete?.id ?? ''}</Code> from the daemon's schedule. <Bold>It will never fire again unless you recreate it via chat.</Bold>
          </>
        }
        expected={confirmDelete?.id ?? ''}
        confirmLabel="Delete job"
        onConfirm={() => {
          const jid = confirmDelete?.id;
          setConfirmDelete(null);
          if (jid) remove(jid);
        }}
      />
    </SafeAreaView>
  );
}
