import { View } from 'react-native';

import { AlpiMark } from '../../components/AlpiMark';
import { useTheme } from '../../theme/ThemeContext';

const MARK_SIZE = 96;

export function HomePane() {
  const { colors } = useTheme();
  return (
    <View
      style={{
        flex: 1,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: colors.bg,
      }}
    >
      <AlpiMark size={MARK_SIZE} color={colors.line2} />
    </View>
  );
}
