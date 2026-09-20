import {
  nativeFace,
  palettes as sharedPalettes,
  radii as sharedRadii,
  space as sharedSpace,
  spaceExtra,
} from '../../../common/tokens.mjs';

// Runtime consumers must read useTheme().fontSizes — these raw values ignore the user's text-size setting.
export {
  alpha,
  dotSize,
  fontSizes,
  glyphSize,
  glyphSizeMd,
  lineHeights,
  status,
  typography,
} from '../../../common/tokens.mjs';

// In RN each weight is a separate font family — never use fontWeight on custom fonts.
export const fonts = {
  sans: {
    regular: nativeFace('sans', '400Regular'),
    medium: nativeFace('sans', '500Medium'),
    semibold: nativeFace('sans', '600SemiBold'),
    bold: nativeFace('sans', '700Bold'),
  },
  mono: nativeFace('mono', '400Regular'),
  monoMedium: nativeFace('mono', '500Medium'),
  monoSemibold: nativeFace('mono', '600SemiBold'),
};

// em multipliers — apply as fontSize * tracking.<tier>
export const tracking = {
  tight: -0.018,
  snug: -0.005,
  wide: 0.06,
  wider: 0.1,
};

export const iconSizes = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 20,
  xl: 24,
  hero: 44,
};

export const iconStroke = 2;

export const space = { ...sharedSpace, ...spaceExtra.mobile };

export const pulseDuration = 1600;

export const radii = { ...sharedRadii, bubble: 18, sheet: 28 };

export const motion = {
  ease: 'easeInOut',
  duration: { fast: 120, base: 180, slow: 240 },
};

export const mobile = {
  tap: 44,
  inputH: 44,
  btnH: 48,
  iconBtn: 44,
  bubbleMaxPct: 0.82,
  composerPad: { x: 12, y: 8 },
};

export const PALETTE_OVERRIDES = {
  'light.bg': [
    '#ffffff',
    'desktop bg is the canvas its floating panes sit on; every mobile screen is edge-to-edge, so bg doubles as the pane',
  ],
  'light.bgInput': [
    '#f1f3f5',
    'mobile consumers fill borderless buttons and chips with bgInput, which desktop white would erase on a white ground',
  ],
  'dark.bgInput': [
    '#1a1f26',
    'follows light.bgInput: mobile raises the input above bgElev where desktop recesses it below',
  ],
};

function withOverrides(mode) {
  const out = { ...sharedPalettes[mode] };
  for (const [path, [value]] of Object.entries(PALETTE_OVERRIDES)) {
    const [scope, key] = path.split('.');
    if (scope === mode) out[key] = value;
  }
  return out;
}

export const palettes = {
  light: withOverrides('light'),
  dark: withOverrides('dark'),
};

export const shadows = {
  light: {
    base: {
      shadowColor: '#0b1117',
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: 0.08,
      shadowRadius: 24,
      elevation: 8,
    },
    sm: {
      shadowColor: '#0b1117',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.06,
      shadowRadius: 2,
      elevation: 1,
    },
  },
  dark: {
    base: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: 0.6,
      shadowRadius: 30,
      elevation: 8,
    },
    sm: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 0 },
      shadowOpacity: 0.4,
      shadowRadius: 0.5,
      elevation: 1,
    },
  },
};
