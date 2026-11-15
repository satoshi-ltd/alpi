import { Text } from 'react-native';

import { typeLeading } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';

export function Eyebrow({ color, style, children, ...rest }) {
  const { colors, fonts, fontSizes } = useTheme();
  const merged = Object.assign(
    {
      fontFamily: fonts.sans.medium,
      fontSize: fontSizes.sm,
      lineHeight: Math.round(fontSizes.sm * typeLeading.small),
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
