import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useRef } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../src/theme/tokens';

import { Row, RowGroup, RowSeparator } from '../../../../src/components/Row';
import { PanelHeader } from '../../../../src/features/profile/PanelHeader';
import { StatusWord } from '../../../../src/features/profile/StatusWord';
import { useBack } from '../../../../src/hooks/useBack';
import { useScheduleList } from '../../../../src/hooks/useDaemonData';
import { usePullRefresh } from '../../../../src/hooks/usePullRefresh';
import { useEventEffect } from '../../../../src/hooks/useEvents';
import { formatLastRun, jobFailed, jobTitle } from '../../../../src/lib/scheduleFormat';
import { describeWhen } from '../../../../../common/schedule.mjs';
import { useTheme } from '../../../../src/theme/ThemeContext';
import { EMPTY } from '../../../../../common/emptyCopy.mjs';

export default function ScheduleList() {
  const { id, job } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const { colors, fonts, fontSizes } = useTheme();
  const pull = usePullRefresh(() => schedule.refresh?.());
  const schedule = useScheduleList(id);
  const jobs = schedule.data?.jobs ?? [];
  const linked = useRef(false);
  const loadError = schedule.error ? String(schedule.error?.message ?? schedule.error) : null;

  const open = (jid) => router.push({ pathname: `/profile/${id}/schedule/[job]`, params: { job: String(jid) } });

  useEffect(() => {
    if (linked.current || !job) return;
    linked.current = true;
    open(job);
  }, [job]);

  useEventEffect(['schedule.done', 'schedule.failed', 'schedule.changed'], (ev) => {
    if (ev.data?.profile === id) schedule.refresh();
  });

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <PanelHeader profile={id} section="SCHEDULES" count={jobs.length} onBack={goBack} />
      <ScrollView refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />} contentContainerStyle={{ paddingBottom: space.s9 }}>
        {schedule.loading && jobs.length === 0 && !loadError ? (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : loadError ? (
          <View style={{ padding: space.s8, gap: space.s2 }}>
            <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: colors.dangerText }}>
              Could not load schedule
            </Text>
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>
              {loadError}
            </Text>
          </View>
        ) : (
          <RowGroup style={{ marginTop: space.s5 }}>
            {jobs.length === 0 ? (
              <Row label={EMPTY.schedule.title} helper={EMPTY.schedule.hint} chevron={false} />
            ) : (
              jobs.map((j, i) => {
                const paused = !!j.paused;
                const failed = jobFailed(j);
                return (
                  <View key={j.id}>
                    {i > 0 ? <RowSeparator /> : null}
                    <Pressable
                      onPress={() => open(j.id)}
                      accessibilityRole="button"
                      accessibilityLabel={`${jobTitle(j)}, ${describeWhen(j)}${paused ? ', paused' : failed ? ', last run failed' : ''}`}
                      android_ripple={{ color: colors.selected }}
                      style={({ pressed }) => ({
                        minHeight: 44,
                        paddingHorizontal: space.s8,
                        paddingVertical: space.s5,
                        gap: space.s1,
                        backgroundColor: pressed ? colors.selected : 'transparent',
                      })}
                    >
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4 }}>
                        <StatusWord word="" on={!paused} />
                        <Text style={{ flex: 1, fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: paused ? colors.ink3 : colors.ink }} numberOfLines={1}>
                          {jobTitle(j)}
                        </Text>
                        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: failed && !paused ? colors.dangerText : colors.ink3 }} numberOfLines={1}>
                          {paused ? 'paused' : failed ? 'failed' : j.last_run_at ? formatLastRun(j.last_run_at, j.last_run_status).replace(/^ran /, '') : ''}
                        </Text>
                      </View>
                      <Text style={{ marginLeft: space.s6, fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }} numberOfLines={1}>
                        {describeWhen(j)}
                      </Text>
                    </Pressable>
                  </View>
                );
              })
            )}
          </RowGroup>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
