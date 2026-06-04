import Svg, { Circle, Line, Path, Rect } from 'react-native-svg';

import { useTheme } from '../theme/ThemeContext';
import { ICONS, ICON_ALIASES } from './iconPaths';

const TAG = { path: Path, circle: Circle, rect: Rect, line: Line };
// Mobile nav uses chevrons for back/forward (desktop's "back" is an arrow-left).
const ALIASES = { ...ICON_ALIASES, back: 'chevron-left', forward: 'chevron-right' };

export function Icon({ name, size = 22, color, strokeWidth = 2 }) {
  const { colors } = useTheme();
  const tint = color ?? colors.ink2;
  const def = ICONS[ALIASES[name] ?? name];
  if (!def) return null;
  const els = Array.isArray(def) ? def : def.els;
  const vb = (!Array.isArray(def) && def.vb) || '0 0 24 24';
  const sw = !Array.isArray(def) && def.sw != null ? def.sw : strokeWidth;
  const filled = !Array.isArray(def) && def.fill === 'currentColor';
  return (
    <Svg
      width={size}
      height={size}
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
