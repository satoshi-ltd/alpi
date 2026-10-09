import { Text, View } from 'react-native';

import { space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';

export function NothingSelected({ children }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s10 }}>
      <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3, textAlign: 'center' }}>{children}</Text>
    </View>
  );
}
