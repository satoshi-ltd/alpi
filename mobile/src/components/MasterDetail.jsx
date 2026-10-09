import { View } from 'react-native';

import { LIST_COLUMN_W } from '../lib/panes';
import { useTheme } from '../theme/ThemeContext';

export function MasterDetail({ list, detail }) {
  const { colors } = useTheme();
  return (
    <View style={{ flex: 1, flexDirection: 'row' }}>
      <View testID="master-list" style={{ width: LIST_COLUMN_W, borderRightWidth: 0.5, borderRightColor: colors.line }}>{list}</View>
      <View testID="master-detail" style={{ flex: 1, minWidth: 0 }}>{detail}</View>
    </View>
  );
}
