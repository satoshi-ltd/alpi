import { Pressable, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AlpiMark } from '../../components/AlpiMark';
import { Icon } from '../../components/Icon';
import { CHROME_BTN, tapSlop } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { radii, space } from '../../theme/tokens';

const MARK_SIZE = 96;

export function HomePane() {
  const { colors } = useTheme();
  const { twoPane, sidebarOpen, toggleSidebar } = usePane();
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
            borderRadius: radii.md,
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: pressed ? colors.selected : 'transparent',
            zIndex: 1,
          })}
        >
          <Icon name="panel-left" size="lg" color={colors.ink2} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <AlpiMark size={MARK_SIZE} color={colors.line2} />
      </View>
    </SafeAreaView>
  );
}
