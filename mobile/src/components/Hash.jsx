import Svg, { Path } from 'react-native-svg';

import { useTheme } from '../theme/ThemeContext';

// Hash glyph drawn as SVG strokes — geometric centering exact across iOS/Android. Custom-font `<Text>` has uneven baseline metrics on iOS (JetBrains Mono `#` reserves descender space even though `#` has no descender), so the character looks low/left even with textAlign center + lineHeight tight. Drawing as paths sidesteps it.
export function Hash({ color, size = 18 }) {
  const { colors } = useTheme();
  const stroke = color ?? colors.ink3;
  // viewBox 0..18 with 4 strokes: 2 horizontal (y=7, y=11) + 2 slanted verticals (slope -2 over the height).
  return (
    <Svg width={size} height={size} viewBox="0 0 18 18" fill="none">
      <Path
        d="M3 7h12M3 11h12M7 3l-1.5 12M13 3l-1.5 12"
        stroke={stroke}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
