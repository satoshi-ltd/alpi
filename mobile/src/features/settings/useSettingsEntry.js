import { useRouter } from 'expo-router';
import { useCallback } from 'react';

import { useCanAdminEarly } from '../../hooks/useActiveRole';
import { openVerb } from '../../lib/panes';

export const SETTINGS_PATH = '/settings';

export function useSettingsEntry({ twoPane, pathname, showSheet }) {
  const canAdmin = useCanAdminEarly();
  const router = useRouter();

  // AdminGuard refuses a member the route — the sheet keeps sign out reachable
  return useCallback(() => {
    if (!twoPane || !canAdmin) {
      showSheet(true);
      return;
    }
    showSheet(false);
    router[openVerb({ twoPane, pathname })](SETTINGS_PATH);
  }, [twoPane, canAdmin, showSheet, router, pathname]);
}
