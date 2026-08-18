import { usePathname, useRouter } from 'expo-router';

import { isPaneRoot } from '../lib/panes';
import { usePane } from '../nav/PaneContext';

export function useShowBack(onBack) {
  const { twoPane } = usePane();
  const pathname = usePathname();
  const router = useRouter();

  return !!onBack && (!twoPane || (!isPaneRoot(pathname) && router.canGoBack()));
}
