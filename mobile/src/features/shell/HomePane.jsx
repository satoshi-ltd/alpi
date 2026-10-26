import { useState } from 'react';
import { Pressable, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ALPACA_FOLD } from '../../../../common/folds.mjs';
import { EmptyState } from '../../components/EmptyState';
import { Fold } from '../../components/Fold';
import { Icon } from '../../components/Icon';
import { useIsAdmin } from '../../hooks/useActiveRole';
import { CHROME_BTN, tapSlop } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { radii, space } from '../../theme/tokens';
import { CreateProfileSheet } from '../sheets/CreateProfileSheet';

const MARK_SIZE = 96;
const MARK_OPACITY = 0.16;

export function HomePane() {
  const { colors } = useTheme();
  const { twoPane, sidebarOpen, toggleSidebar } = usePane();
  const isAdmin = useIsAdmin();
  const [creating, setCreating] = useState(false);
  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      {twoPane && !sidebarOpen ? (
        <Pressable
          onPress={toggleSidebar}
          hitSlop={tapSlop(CHROME_BTN)}
          accessibilityRole="button"
          accessibilityLabel="Show sidebar"
          style={({ pressed }) => ({
            position: 'absolute',
            top: space.s5,
            left: space.s5,
            width: CHROME_BTN,
            height: CHROME_BTN,
            borderRadius: radii.xs,
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: pressed ? colors.selected : 'transparent',
            zIndex: 1,
          })}
        >
          <Icon name="panel-left" size="md" color={colors.ink2} />
        </Pressable>
      ) : null}
      <EmptyState
        mark={(
          <View style={{ opacity: MARK_OPACITY }}>
            <Fold fold={ALPACA_FOLD} size={MARK_SIZE} />
          </View>
        )}
        title="Pick a profile or a workgroup"
        detail="Their chats open here."
        action={isAdmin ? { label: 'New profile', onPress: () => setCreating(true) } : null}
      />
      {isAdmin ? <CreateProfileSheet open={creating} onClose={() => setCreating(false)} /> : null}
    </SafeAreaView>
  );
}
