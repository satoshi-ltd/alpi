import {
  fontSizes as sharedFontSizes,
  eyebrow as sharedEyebrow,
  iconSizesAllowed,
  iconStrokeFor as sharedIconStrokeFor,
  motionTokens,
  nativeFace,
  palettes as sharedPalettes,
  radii as sharedRadii,
  space as sharedSpace,
  spaceExtra,
  typography as sharedTypography,
} from '../../../common/tokens.mjs';

export {
  alpha,
  glyphSize,
  glyphSizeMd,
  controlHeight,
  dotScale,
  eyebrow,
  focusRing,
  fontWeights,
  iconSizesAllowed,
  iconStrokeRendered,
  ladderDirection,
  lineHeights,
  spaceScale,
  status,
  typeLadder,
} from '../../../common/tokens.mjs';

export const FONT_SIZE_DROPS = ['xxs', 'label'];
export const FONT_SIZE_ADDS = { chat: 16 };

// Runtime consumers must read useTheme().fontSizes — these raw values ignore the user's text-size setting.
export const fontSizes = Object.fromEntries(
  Object.entries({ ...sharedFontSizes, ...FONT_SIZE_ADDS })
    .filter(([name]) => !FONT_SIZE_DROPS.includes(name))
    .sort((a, b) => a[1] - b[1]),
);

export const typography = {
  ...sharedTypography,
  chat: { ...sharedTypography.chat, size: 'chat' },
};

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
  crease: 'BricolageGrotesque_800ExtraBold',
};

// em multipliers — apply as fontSize * tracking.<tier>
export const tracking = {
  tight: -0.018,
  snug: -0.005,
  wide: 0.06,
  wider: 0.1,
  eyebrow: sharedEyebrow.tracking,
};

export const iconSizes = { xs: iconSizesAllowed.mobile[0], md: iconSizesAllowed.mobile[1] };

export const iconStrokeFor = sharedIconStrokeFor;

// fixed-size chrome: deliberately outside the user/OS text scale so digits never clip the pill
export const countBadge = { size: 18, border: 1.5, fontSize: fontSizes.xs, radius: sharedRadii.xs };

export const space = { ...sharedSpace, ...spaceExtra.mobile };

export const pulseDuration = motionTokens.pulse;

export const radii = { ...sharedRadii };

export const motion = {
  ease: 'easeInOut',
  duration: { fast: motionTokens.fast, base: motionTokens.enter, slow: 240 },
  enter: motionTokens.enter,
  exit: motionTokens.exit,
  easeEnter: motionTokens.easeEnter,
  easeExit: motionTokens.easeExit,
  pulse: motionTokens.pulse,
  pulseLow: motionTokens.pulseLow,
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
    '#f2f2f2',
    'mobile consumers fill borderless buttons and chips with bgInput, which desktop white would erase on a white ground',
  ],
  'dark.bgInput': [
    '#1f1f1f',
    'follows light.bgInput: mobile raises the input above bgElev where desktop recesses it below',
  ],
  'light.field': [
    '#ececec',
    'a field inside a card on the phone reads 1.07:1 over the #f4f4f4 card; the desktop well is #eaeaea at 1.09:1',
  ],
  'dark.card': [
    '#151515',
    'every phone screen is edge-to-edge on bg, so its cards sit lighter than the ground; desktop cards sit below the pane',
  ],
  'dark.field': [
    '#1f1f1f',
    'a phone field inside a dark card steps up to #1f1f1f where the desktop well is a tint over a darker card',
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

const shadowsFor = (mode, shadowColor) => {
  const p = palettes[mode];
  const flat = { shadowColor, shadowOpacity: 0, shadowRadius: 0, elevation: 0 };
  const dialog = { ...flat, borderWidth: 0.5, borderColor: p.ink3 };
  return {
    base: { ...flat, borderWidth: 0.5, borderColor: p.line2 },
    sm: { ...flat, borderWidth: 0.5, borderColor: p.line },
    sheet: { ...flat, borderWidth: 0, borderTopWidth: 1, borderColor: p.edge },
    dialog,
    popover: { ...dialog },
    toast: { ...dialog },
  };
};

export const shadows = {
  light: shadowsFor('light', '#141414'),
  dark: shadowsFor('dark', '#000'),
};

export const veil = (colors) => `${colors.bg}b8`;
