import { usePathname } from 'expo-router';

import { isPaneRoot } from '../lib/panes';
import { usePane } from '../nav/PaneContext';

export function useShowBack(onBack) {
  const { twoPane } = usePane();
  const pathname = usePathname();

  return !!onBack && !(twoPane && isPaneRoot(pathname));
}
