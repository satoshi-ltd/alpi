import {
  fontSizes as sharedFontSizes,
  eyebrow as sharedEyebrow,
  floatShadow,
  iconSizes as sharedIconSizes,
  iconStrokeFor as sharedIconStrokeFor,
  motionTokens,
  nativeFace,
  palettes as sharedPalettes,
  radii as sharedRadii,
  space as sharedSpace,
  typeLadder,
  typography as sharedTypography,
  veils,
} from '../../../common/tokens.mjs';
import { countBadgeSpec } from '../../../common/countBadge.mjs';

export {
  alpha,
  glyphSize,
  glyphSizeMd,
  controlHeight,
  controlRole,
  dotScale,
  eyebrow,
  fieldFocus,
  floatShadow,
  focusRing,
  fontWeights,
  monoScale,
  nestInset,
  retiredRadii,
  shell,
  stateFill,
  stateFills,
  stateMotion,
  surfaces,
  iconSizesAllowed,
  iconStrokeRendered,
  ladderDirection,
  lineHeights,
  spaceScale,
  status,
  touchTarget,
  typeFloor,
  typeLadder,
  typeLeading,
  veils,
} from '../../../common/tokens.mjs';

export const FONT_SIZE_ADDS = { chat: typeLadder.read };

// Runtime consumers must read useTheme().fontSizes — these raw values ignore the user's text-size setting.
export const fontSizes = Object.fromEntries(
  Object.entries({ ...sharedFontSizes, ...FONT_SIZE_ADDS }).sort((a, b) => a[1] - b[1]),
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
  name: 'BricolageGrotesque_800ExtraBold',
};

// em multipliers — apply as fontSize * tracking.<tier>
export const tracking = {
  tight: -0.018,
  snug: -0.005,
  wide: 0.06,
  wider: 0.1,
  eyebrow: sharedEyebrow.tracking,
};

export const iconSizes = { xs: sharedIconSizes.inline, md: sharedIconSizes.control, lg: sharedIconSizes.nav };

export const iconStrokeFor = sharedIconStrokeFor;

// fixed-size chrome: deliberately outside the user/OS text scale so digits never clip the pill
export const countBadge = { size: countBadgeSpec.size.mobile, border: 1.5, fontSize: fontSizes.xs, radius: sharedRadii.pill };

export const space = { ...sharedSpace };

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
  inputH: 48,
  btnH: 48,
  iconBtn: 44,
  bubbleMaxPct: 0.82,
  composerH: 56,
  composerPad: { x: 8, y: 8 },
};

export const palettes = {
  light: { ...sharedPalettes.light },
  dark: { ...sharedPalettes.dark },
};

const FLOAT_NATIVE = {
  light: { shadowColor: '#000', shadowOpacity: 0.1, shadowRadius: 16, shadowOffset: { width: 0, height: 12 }, elevation: 8, borderWidth: 0 },
  dark: { shadowColor: '#000', shadowOpacity: 0.55, shadowRadius: 20, shadowOffset: { width: 0, height: 16 }, elevation: 8, borderWidth: 1, borderColor: 'rgba(237,237,237,0.09)' },
};

const shadowsFor = (mode) => {
  const flat = { shadowColor: '#000', shadowOpacity: 0, shadowRadius: 0, elevation: 0, borderWidth: 0 };
  const float = FLOAT_NATIVE[mode];
  return {
    base: { ...flat },
    sm: { ...flat },
    sheet: { ...float },
    dialog: { ...float },
    popover: { ...float },
    toast: { ...float },
  };
};

export const shadows = {
  light: shadowsFor('light'),
  dark: shadowsFor('dark'),
};

export const veil = (colors) => (colors?.ink === sharedPalettes.dark.ink ? veils.dark : veils.light);
