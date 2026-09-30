import { useFocusEffect, usePathname, useRouter } from 'expo-router';
import { useCallback } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ScreenHeader } from '../src/components/ScreenHeader';
import { ActivityList } from '../src/features/shell/ActivityList';
import { useActivity } from '../src/hooks/useActivity';
import { useBack } from '../src/hooks/useBack';
import { usePullRefresh } from '../src/hooks/usePullRefresh';
import { focusRequest } from '../src/hooks/useRequestQueue';
import { openVerb } from '../src/lib/panes';
import { usePane } from '../src/nav/PaneContext';
import { useTheme } from '../src/theme/ThemeContext';

export default function ActivityScreen() {
  const { colors } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const { twoPane } = usePane();
  const goBack = useBack();
  const { activity, supported, unsupported, refresh } = useActivity();
  const { refreshing, onRefresh } = usePullRefresh(refresh);

  useFocusEffect(useCallback(() => { refresh(); }, [refresh]));

  const open = useCallback((target) => {
    if (target.type === 'request') {
      focusRequest(target.domain, target.requestId);
      return;
    }
    router[openVerb({ twoPane, pathname })](target.path);
  }, [router, twoPane, pathname]);

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title="Activity" subtitle="ACROSS PROFILES" onBack={goBack} />
      <ActivityList
        activity={activity}
        supported={supported}
        unsupported={unsupported}
        onOpen={open}
        refreshing={refreshing}
        onRefresh={onRefresh}
      />
    </SafeAreaView>
  );
}
