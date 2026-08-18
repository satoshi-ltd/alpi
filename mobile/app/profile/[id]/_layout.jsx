import { Stack } from 'expo-router';
import { useMemo } from 'react';

import { AdminGuard } from '../../../src/components/AdminGuard';
import { stackAnimation } from '../../../src/lib/panes';
import { usePane } from '../../../src/nav/PaneContext';

export default function ProfileSettingsLayout() {
  const { twoPane } = usePane();
  // Never key or wrap <Stack> — a remount drops navigation state.
  const screenOptions = useMemo(
    () => ({ headerShown: false, animation: stackAnimation(twoPane) }),
    [twoPane],
  );

  return (
    <AdminGuard>
      <Stack screenOptions={screenOptions} />
    </AdminGuard>
  );
}
