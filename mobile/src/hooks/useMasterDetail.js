import { useWindowDimensions } from 'react-native';

import { isMasterDetail } from '../lib/panes';
import { usePane } from '../nav/PaneContext';

export function useMasterDetail() {
  const { width } = useWindowDimensions();
  const { twoPane, sidebarOpen } = usePane();
  return isMasterDetail(width, twoPane, sidebarOpen);
}
