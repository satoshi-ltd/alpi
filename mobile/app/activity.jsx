import { useFocusEffect } from 'expo-router';
import { useCallback } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { pluralize } from '../../common/pluralize.mjs';
import { useConfirm } from '../src/components/ConfirmProvider';
import { LoadFailed } from '../src/components/LoadFailed';
import { ScreenHeader } from '../src/components/ScreenHeader';
import { useToast } from '../src/components/Toast';
import { ActivityList } from '../src/features/shell/ActivityList';
import { useActivityActions } from '../src/features/shell/useActivityActions';
import { useActiveRole } from '../src/hooks/useActiveRole';
import { useActivity } from '../src/hooks/useActivity';
import { useBack } from '../src/hooks/useBack';
import { useEndpoint } from '../src/lib/EndpointContext';
import { usePullRefresh } from '../src/hooks/usePullRefresh';
import { useTheme } from '../src/theme/ThemeContext';

export default function ActivityScreen() {
  const { colors } = useTheme();
  const goBack = useBack();
  const { activity, supported, unsupported, loadError, refresh } = useActivity();
  const { refreshing, onRefresh } = usePullRefresh(refresh);
  const { open, fireJob } = useActivityActions(refresh);
  const { endpoint } = useEndpoint();
  const toast = useToast();
  const confirm = useConfirm();
  const canRetry = useActiveRole() === 'admin';

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
          confirm={confirm}
          canRetry={canRetry}
          onRetry={fireJob}
          onRetried={(started) => {
            if (started) toast({ message: `Retrying ${started} ${pluralize(started, 'job')}`, kind: 'success' });
            refresh();
          }}
          connectionId={endpoint?.id ?? null}
          refreshing={refreshing}
          onRefresh={onRefresh}
        />
      )}
    </SafeAreaView>
  );
}
