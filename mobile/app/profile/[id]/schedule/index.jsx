import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { MasterDetail } from '../../../../src/components/MasterDetail';
import { NothingSelected } from '../../../../src/components/NothingSelected';
import { PanelHeader } from '../../../../src/features/profile/PanelHeader';
import { JobDetail } from '../../../../src/features/schedule/JobDetail';
import { JobList } from '../../../../src/features/schedule/JobList';
import { useBack } from '../../../../src/hooks/useBack';
import { useScheduleList } from '../../../../src/hooks/useDaemonData';
import { useMasterDetail } from '../../../../src/hooks/useMasterDetail';
import { useTheme } from '../../../../src/theme/ThemeContext';
import { jobGroups } from '../../../../../common/attention.mjs';

export default function ScheduleList() {
  const { id, job } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const { colors } = useTheme();
  const schedule = useScheduleList(id);
  const wide = useMasterDetail();
  const handled = useRef(null);
  const [picked, setPicked] = useState(job ? String(job) : null);
  const jobs = schedule.data?.jobs ?? [];
  const first = jobGroups(jobs).find((group) => group.jobs.length)?.jobs[0]?.id;
  const known = picked != null && jobs.some((j) => String(j.id) === picked);
  const selected = known ? picked : first != null ? String(first) : null;
  const settled = !schedule.loading && !schedule.error;
  const open = (jid) => router.push({ pathname: `/profile/${id}/schedule/[job]`, params: { job: String(jid) } });

  useEffect(() => {
    if (!job) return;
    const key = String(job);
    if (handled.current === key) return;
    handled.current = key;
    if (wide) setPicked(key);
    else open(key);
  }, [job, wide]);

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <PanelHeader profile={id} section="SCHEDULES" count={jobs.length} onBack={goBack} />
      {wide ? (
        <MasterDetail
          list={<JobList profile={id} selectedId={selected} onOpen={(jid) => setPicked(String(jid))} embedded />}
          detail={selected ? <JobDetail key={selected} profile={id} jobId={selected} embedded onGone={() => setPicked(null)} /> : settled ? <NothingSelected>No scheduled jobs</NothingSelected> : null}
        />
      ) : (
        <JobList profile={id} onOpen={open} />
      )}
    </SafeAreaView>
  );
}
