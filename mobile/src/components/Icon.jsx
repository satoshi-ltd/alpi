import Svg, { Circle, Line, Path, Rect } from 'react-native-svg';

import { iconSizes, iconStroke } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { ICONS, ICON_ALIASES } from './iconPaths';

const TAG = { path: Path, circle: Circle, rect: Rect, line: Line };
// Mobile nav uses chevrons for back/forward (desktop's "back" is an arrow-left).
const ALIASES = { ...ICON_ALIASES, back: 'chevron-left', forward: 'chevron-right' };

export function Icon({ name, size = 'md', color, strokeWidth }) {
  const { colors } = useTheme();
  const tint = color ?? colors.ink2;
  const def = ICONS[ALIASES[name] ?? name];
  if (!def) return null;
  const els = Array.isArray(def) ? def : def.els;
  const vb = (!Array.isArray(def) && def.vb) || '0 0 24 24';
  const px = typeof size === 'number' ? size : iconSizes[size] ?? iconSizes.md;
  const sw =
    strokeWidth ?? (!Array.isArray(def) && def.sw != null ? def.sw : iconStroke);
  const filled = !Array.isArray(def) && def.fill === 'currentColor';
  return (
    <Svg
      width={px}
      height={px}
      viewBox={vb}
      fill={filled ? tint : 'none'}
      stroke={sw === 0 ? 'none' : tint}
      strokeWidth={sw}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {els.map(([tag, attrs], i) => {
        const C = TAG[tag];
        const a = attrs.fill === 'currentColor' ? { ...attrs, fill: tint } : attrs;
        return <C key={i} {...a} />;
      })}
    </Svg>
  );
}
