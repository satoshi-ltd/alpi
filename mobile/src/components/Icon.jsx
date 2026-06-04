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
  check: 'M5 12l4 4L19 7',
  ban: 'M7.05 7.05l9.9 9.9',
  paperclip: 'm16 6-8.414 8.586a2 2 0 0 0 2.829 2.829l8.414-8.586a4 4 0 1 0-5.657-5.657l-8.379 8.551a6 6 0 1 0 8.485 8.485l8.379-8.551',
};

const FILE_BODY = (
  <>
    <Path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" />
    <Path d="M14 2v5a1 1 0 0 0 1 1h5" />
  </>
);

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
  ban: <Circle cx="12" cy="12" r="7" />,
  circle: <Circle cx="12" cy="12" r="7" />,
  file: FILE_BODY,
  'file-text': <>{FILE_BODY}<Path d="M10 9H8" /><Path d="M16 13H8" /><Path d="M16 17H8" /></>,
  'file-code': <>{FILE_BODY}<Path d="M10 12.5 8 15l2 2.5" /><Path d="m14 12.5 2 2.5-2 2.5" /></>,
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
