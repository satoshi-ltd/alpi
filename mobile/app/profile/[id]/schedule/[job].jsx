import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { JobDetail } from '../../../../src/features/schedule/JobDetail';
import { useBack } from '../../../../src/hooks/useBack';
import { useMasterDetail } from '../../../../src/hooks/useMasterDetail';
import { useTheme } from '../../../../src/theme/ThemeContext';

export default function ScheduleJob() {
  const { id, job } = useLocalSearchParams();
  const goBack = useBack();
  const { colors } = useTheme();
  const router = useRouter();
  const wide = useMasterDetail();
  useEffect(() => {
    if (wide && job) router.replace({ pathname: `/profile/${id}/schedule`, params: { job: String(job) } });
  }, [wide, id, job, router]);
  if (wide) return null;
  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <JobDetail profile={id} jobId={job} onBack={goBack} onGone={goBack} />
    </SafeAreaView>
  );
}
