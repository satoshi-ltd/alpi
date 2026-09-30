import { useEffect, useMemo, useRef } from 'react';
import { View, useWindowDimensions } from 'react-native';
import Animated, { useAnimatedStyle } from 'react-native-reanimated';

import { useSidebarOpen } from '../../hooks/useSidebarOpen';
import { useTwoPane } from '../../hooks/useTwoPane';
import { SIDEBAR_W } from '../../lib/panes';
import { usePresence } from '../../lib/usePresence';
import { PaneContext } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { motionMs } from '../../theme/tokens';
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

  const lastTwoPane = useRef(twoPane);
  const snap = lastTwoPane.current !== twoPane;
  useEffect(() => {
    lastTwoPane.current = twoPane;
  }, [twoPane]);
  const shown = twoPane && open;
  const { mounted, progress } = usePresence(shown, motionMs.sidebar, { snap });
  const slide = useAnimatedStyle(() => ({ transform: [{ translateX: SIDEBAR_W * (progress.value - 1) }] }));

  return (
    <PaneContext.Provider value={pane}>
      <View style={{ flex: 1, flexDirection: 'row', backgroundColor: colors.bg }}>
        <View testID="sidebar-space" style={{ width: mounted ? SIDEBAR_W : 0 }} />
        <View style={{ flex: 1, minWidth: 0 }}>{children}</View>
        {mounted ? (
          <Animated.View
            testID="sidebar-layer"
            style={[{ position: 'absolute', top: 0, bottom: 0, left: 0, width: SIDEBAR_W, flexDirection: 'row' }, slide]}
          >
            <SidebarPane onCollapse={toggle} />
          </Animated.View>
        ) : null}
      </View>
    </PaneContext.Provider>
  );
}
