import { profileAccents } from './accents';

// In RN each weight is a separate font family — never use fontWeight on custom fonts; reference fonts.sans.medium / fonts.monoSemibold etc.
export const fonts = {
  sans: {
    regular: 'Inter_400Regular',
    medium: 'Inter_500Medium',
    semibold: 'Inter_600SemiBold',
    bold: 'Inter_700Bold',
  },
  // Mono regular kept as a plain string for back-compat with callers using `fontFamily: fonts.mono`.
  mono: 'JetBrainsMono_400Regular',
  monoMedium: 'JetBrainsMono_500Medium',
  monoSemibold: 'JetBrainsMono_600SemiBold',
};

// 1:1 with desktop --fs-* (`2xl` is desktop's --fs-xxl); only --fs-hero has no mobile counterpart. Runtime consumers must read useTheme().fontSizes — these raw values ignore the user's text-size setting.
export const fontSizes = {
  xxs: 9,
  xs: 11,
  sm: 12,
  base: 13,
  md: 14,
  lg: 15,
  xl: 18,
  xxl: 22,
  display: 28,
};

// Multipliers aligned with desktop --lh-*. Applied as fontSize * lineHeights.<tier>.
// tight: controls / chips / single-line labels. cozy: UI titles, pills, tooltips.
// normal: inputs, paragraphs. relaxed: long-form prose, message bodies.
export const lineHeights = {
  tight: 1,
  cozy: 1.3,
  normal: 1.5,
  relaxed: 1.65,
};

// Desktop's letter-spacings in em — apply as fontSize * tracking.<tier>
export const tracking = {
  tight: -0.018,
  snug: -0.005,
  wide: 0.06,
  wider: 0.1,
};

// Desktop's Icon SIZES keys, one notch up for 14–15px body and the 44pt tap target
export const iconSizes = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 20,
  xl: 24,
  hero: 44,
};

export const iconStroke = 2;

export const space = {
  s1: 4,
  s2: 6,
  s3: 8,
  s4: 10,
  s5: 12,
  s6: 14,
  s7: 16,
  s8: 20,
  s9: 24,
  s10: 28,
  s11: 36,
};

export const dotSize = 7;
export const glyphSize = 8;
export const glyphSizeMd = 14;
export const pulseDuration = 1600;

export const radii = {
  xs: 4,
  sm: 6,
  md: 8,
  lg: 10,
  xl: 12,
  '2xl': 14,
  '3xl': 16,
  bubble: 22,
  sheet: 28,
  pill: 999,
};

export const status = {
  success: '#3fb37a',
  warning: '#d4b443',
  danger: '#c14545',
};

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

const lightColors = {
  bg: '#ffffff',
  bgPane: '#ffffff',
  bgSide: '#f5f6f8',
  bgElev: '#ffffff',
  bgInput: '#f1f3f5',
  ink: '#0b1117',
  ink2: '#3d4955',
  ink3: '#7c8896',
  ink4: '#b1bac4',
  line: 'rgba(11,17,23,0.07)',
  line2: 'rgba(11,17,23,0.14)',
  hover: 'rgba(11,17,23,0.04)',
  selected: 'rgba(11,17,23,0.06)',
};

const darkColors = {
  bg: '#0a0d11',
  bgPane: '#11151a',
  bgSide: '#0c1014',
  bgElev: '#161b22',
  bgInput: '#1a1f26',
  ink: '#e6edf3',
  ink2: '#b1bac4',
  ink3: '#7d8590',
  ink4: '#484f58',
  line: 'rgba(230,237,243,0.08)',
  line2: 'rgba(230,237,243,0.16)',
  hover: 'rgba(230,237,243,0.04)',
  selected: 'rgba(230,237,243,0.07)',
};

// Never collapse these to one constant: the raw brand gold is 2.44:1 on the SyncBar track over white.
const accents = {
  light: { accent: '#9c7a33' },
  dark: { accent: profileAccents.alpi },
};

export const palettes = {
  light: { ...lightColors, ...status, ...accents.light },
  dark: { ...darkColors, ...status, ...accents.dark },
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

export const alpha = {
  faint: 0.35,
  disabled: 0.45,
  muted: 0.55,
  soft: 0.7,
};
