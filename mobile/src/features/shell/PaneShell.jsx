import { useMemo } from 'react';
import { View } from 'react-native';

import { useTwoPane } from '../../hooks/useTwoPane';
import { PaneContext } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { SidebarPane } from './SidebarPane';

export function PaneShell({ children }) {
  const { colors } = useTheme();
  const twoPane = useTwoPane();
  const pane = useMemo(() => ({ twoPane, side: twoPane ? 'detail' : 'full' }), [twoPane]);

  return (
    <PaneContext.Provider value={pane}>
      <View style={{ flex: 1, flexDirection: 'row', backgroundColor: colors.bg }}>
        {twoPane ? <SidebarPane /> : null}
        <View style={{ flex: 1, minWidth: 0 }}>{children}</View>
      </View>
    </PaneContext.Provider>
  );
}
