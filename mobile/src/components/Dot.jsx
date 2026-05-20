import { View } from 'react-native';

import { useTheme } from '../theme/ThemeContext';

export function Dot({ color, size = 7 }) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: color ?? colors.ink3,
      }}
    />
  );
}
