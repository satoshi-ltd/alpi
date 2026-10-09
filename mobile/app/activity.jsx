import { useFocusEffect } from 'expo-router';
import { useCallback } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LoadFailed } from '../src/components/LoadFailed';
import { ScreenHeader } from '../src/components/ScreenHeader';
import { ActivityList } from '../src/features/shell/ActivityList';
import { useActivityActions } from '../src/features/shell/useActivityActions';
import { useActivity } from '../src/hooks/useActivity';
import { useBack } from '../src/hooks/useBack';
import { usePullRefresh } from '../src/hooks/usePullRefresh';
import { useTheme } from '../src/theme/ThemeContext';

export default function ActivityScreen() {
  const { colors } = useTheme();
  const goBack = useBack();
  const { activity, supported, unsupported, loadError, refresh } = useActivity();
  const { refreshing, onRefresh } = usePullRefresh(refresh);
  const { open, runAgain } = useActivityActions(refresh);

  useFocusEffect(useCallback(() => { refresh(); }, [refresh]));

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title="Activity" subtitle="ACROSS PROFILES" onBack={goBack} />
      {loadError ? (
        <LoadFailed label="activity" error={loadError} onRetry={refresh} />
      ) : (
        <ActivityList
          activity={activity}
          supported={supported}
          unsupported={unsupported}
          onOpen={open}
          onRun={runAgain}
          refreshing={refreshing}
          onRefresh={onRefresh}
        />
      )}
    </SafeAreaView>
  );
}
