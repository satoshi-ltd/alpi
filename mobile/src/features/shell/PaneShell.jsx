import { useMemo } from 'react';
import { View, useWindowDimensions } from 'react-native';

import { useSidebarOpen } from '../../hooks/useSidebarOpen';
import { useTwoPane } from '../../hooks/useTwoPane';
import { PaneContext } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { SidebarPane } from './SidebarPane';

export function PaneShell({ children }) {
  const { colors } = useTheme();
  const { width, height } = useWindowDimensions();
  const twoPane = useTwoPane();
  const { open, toggle } = useSidebarOpen(width, twoPane, height);
  const pane = useMemo(
    () => ({
      twoPane,
      side: twoPane ? 'detail' : 'full',
      sidebarOpen: open,
      toggleSidebar: toggle,
    }),
    [twoPane, open, toggle],
  );

  return (
    <PaneContext.Provider value={pane}>
      <View style={{ flex: 1, flexDirection: 'row', backgroundColor: colors.bg }}>
        {twoPane && open ? <SidebarPane onCollapse={toggle} /> : null}
        <View style={{ flex: 1, minWidth: 0 }}>{children}</View>
      </View>
    </PaneContext.Provider>
  );
}
