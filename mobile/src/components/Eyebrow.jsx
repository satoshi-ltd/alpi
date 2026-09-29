import { Text } from 'react-native';

import { lineHeights, tracking } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';

export function Eyebrow({ color, style, children, ...rest }) {
  const { colors, fonts, fontSizes } = useTheme();
  const merged = Object.assign(
    {
      fontFamily: fonts.monoMedium,
      fontSize: fontSizes.xs,
      lineHeight: fontSizes.xs * lineHeights.tight,
      letterSpacing: fontSizes.xs * tracking.wide,
      textTransform: 'uppercase',
      color: color ?? colors.ink3,
    },
    ...[style].flat().filter(Boolean),
  );
  return (
    <Text {...rest} style={merged}>
      {children}
    </Text>
  );
}
