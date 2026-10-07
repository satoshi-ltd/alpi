import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useRef } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../src/theme/tokens';

import { Dot } from '../../../../src/components/Dot';
import { Row, RowGroup, RowSeparator, SectionHeader } from '../../../../src/components/Row';
import { PanelHeader } from '../../../../src/features/profile/PanelHeader';
import { StatusWord } from '../../../../src/features/profile/StatusWord';
import { useBack } from '../../../../src/hooks/useBack';
import { useScheduleList } from '../../../../src/hooks/useDaemonData';
import { usePullRefresh } from '../../../../src/hooks/usePullRefresh';
import { useEventEffect } from '../../../../src/hooks/useEvents';
import { jobTitle } from '../../../../src/lib/scheduleFormat';
import { jobGroups, nextRunWord } from '../../../../../common/attention.mjs';
import { describeWhen } from '../../../../../common/schedule.mjs';
import { useTheme } from '../../../../src/theme/ThemeContext';
import { EMPTY } from '../../../../../common/emptyCopy.mjs';
import { ListSkeleton } from '../../../../src/components/ListSkeleton';

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
          <ListSkeleton rows={3} title="md" helper="sm" label="Loading schedules" style={{ marginTop: space.s5 }} />
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
          jobs.length === 0 ? (
            <RowGroup style={{ marginTop: space.s5 }}>
              <Row label={EMPTY.schedule.title} helper={EMPTY.schedule.hint} chevron={false} />
            </RowGroup>
          ) : (
            jobGroups(jobs).map((g) => (
              <View key={g.id}>
                <SectionHeader>{`${g.label} · ${g.jobs.length}`}</SectionHeader>
                <RowGroup>
                  {g.jobs.map((j, i) => {
                    const paused = !!j.paused;
                    const failed = !paused && j.last_run_status === 'error';
                    const word = nextRunWord(j);
                    const dot = failed ? colors.danger : paused ? colors.ink4 : colors.ink;
                    const description = typeof j.description === 'string' ? j.description.trim() : '';
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
                            justifyContent: 'center',
                            backgroundColor: pressed ? colors.selected : 'transparent',
                          })}
                        >
                          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4 }}>
                            <Dot color={dot} />
                            <Text style={{ flex: 1, fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: paused ? colors.ink3 : colors.ink }} numberOfLines={1}>
                              {jobTitle(j)}
                            </Text>
                            {word ? (
                              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: failed ? colors.dangerText : colors.ink3 }} numberOfLines={1}>
                                {word}
                              </Text>
                            ) : null}
                          </View>
                          {description ? (
                            <Text style={{ marginLeft: space.s6, fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }} numberOfLines={1}>
                              {description}
                            </Text>
                          ) : null}
                        </Pressable>
                      </View>
                    );
                  })}
                </RowGroup>
              </View>
            ))
          )
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
