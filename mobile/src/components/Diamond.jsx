import { View } from 'react-native';

import { useTheme } from '../theme/ThemeContext';

// Spec: 11×11 default, transform rotate 45, border-radius 2, color via --c fallback ink-3.
export function Diamond({ color, size = 11, outlined = false }) {
  const { colors } = useTheme();
  const tint = color ?? colors.ink3;
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: 2,
        transform: [{ rotate: '45deg' }],
        backgroundColor: outlined ? 'transparent' : tint,
        borderWidth: outlined ? 1.5 : 0,
        borderColor: outlined ? tint : 'transparent',
      }}
    />
  );
}
