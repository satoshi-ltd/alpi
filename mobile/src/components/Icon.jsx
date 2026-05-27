import Svg, { Circle, Path, Rect } from 'react-native-svg';

import { useTheme } from '../theme/ThemeContext';

const PATHS = {
  bell: 'M6 16V10a6 6 0 1112 0v6l2 2H4l2-2zM10 19a2 2 0 004 0',
  gear: 'M12 3v2M12 19v2M3 12h2M19 12h2M6 6l1.5 1.5M16.5 16.5L18 18M6 18l1.5-1.5M16.5 7.5L18 6',
  back: 'M14 6l-6 6 6 6',
  forward: 'M10 6l6 6-6 6',
  plus: 'M12 5v14M5 12h14',
  search: 'M16 16l4 4',
  mic: 'M5 11a7 7 0 0014 0M12 18v3',
  send: 'M12 19V5M6 11l6-6 6 6',
  camera: 'M9 7l1.5-2h3L15 7',
  more: '',
  chevright: 'M6 4l4 4-4 4',
  'chevron-down': 'M6 9l6 6 6-6',
  cpu: 'M4 4h16v16H4zM8 8h8v8H8zM4 8h2M4 16h2M20 8h-2M20 16h-2M8 4v2M16 4v2M8 20v2M16 20v2',
  wifi: 'M2 9a15 15 0 0120 0M5 13a10 10 0 0114 0M8.5 16.5a5 5 0 017 0',
  x: 'M6 6l12 12M18 6L6 18',
  edit: 'M16.5 3.75l3.75 3.75L9 18.75H5.25V15z',
  // Clock — circle outline (in EXTRAS) + two hands at 12 + 4 to read as "recent / sessions".
  clock: 'M12 7v5l3 2',
};

const EXTRAS = {
  gear: <Circle cx="12" cy="12" r="3" />,
  search: <Circle cx="11" cy="11" r="6" />,
  mic: <Rect x="9" y="3" width="6" height="12" rx="3" />,
  camera: <>
    <Path d="M3 7h18v13H3z" />
    <Circle cx="12" cy="13" r="3.5" />
  </>,
  more: <>
    <Circle cx="5" cy="12" r="1.5" />
    <Circle cx="12" cy="12" r="1.5" />
    <Circle cx="19" cy="12" r="1.5" />
  </>,
  wifi: <Circle cx="12" cy="20" r="1" />,
  clock: <Circle cx="12" cy="12" r="9" />,
};

export function Icon({ name, size = 22, color, strokeWidth = 1.7 }) {
  const { colors } = useTheme();
  const tint = color ?? colors.ink2;
  const extra = EXTRAS[name];
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={tint} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      {extra}
      {PATHS[name] ? <Path d={PATHS[name]} /> : null}
    </Svg>
  );
}
