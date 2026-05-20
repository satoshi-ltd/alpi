import { Text } from 'react-native';
import { fontSizes } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';

// Spec `.eyebrow`: 500 10.5/1 mono ink-3, letter-spacing 0.08em, uppercase.
export function Eyebrow({ children, style }) {
  const { colors, fonts , fontSizes} = useTheme();
  return (
    <Text
      style={[
        {
          fontFamily: fonts.monoMedium,
          fontSize: fontSizes.xs,
          lineHeight: 10.5,
          color: colors.ink3,
          letterSpacing: 0.84,
          textTransform: 'uppercase',
        },
        style,
      ]}
    >
      {children}
    </Text>
  );
}
