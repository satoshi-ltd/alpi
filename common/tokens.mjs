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

export const lineHeights = {
  tight: 1,
  cozy: 1.3,
  normal: 1.5,
  relaxed: 1.65,
};

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
};

export const radii = {
  xs: 4,
  sm: 6,
  md: 8,
  lg: 10,
  xl: 12,
  "2xl": 14,
  "3xl": 16,
  pill: 999,
};

export const alpha = {
  faint: 0.35,
  disabled: 0.45,
  muted: 0.55,
  soft: 0.7,
};

export const dotSize = 7;
export const glyphSize = 8;
export const glyphSizeMd = 14;

export const status = {
  success: "#3fb37a",
  warning: "#d4b443",
  danger: "#c14545",
};

const accent = "#b8954a";

const light = {
  bg: "#eef0f2",
  bgPane: "#ffffff",
  bgSide: "#f5f6f8",
  bgElev: "#ffffff",
  bgInput: "#ffffff",
  ink: "#0b1117",
  ink2: "#3d4955",
  ink3: "#7c8896",
  ink4: "#b1bac4",
  line: "rgba(11,17,23,0.07)",
  line2: "rgba(11,17,23,0.14)",
  hover: "rgba(11,17,23,0.04)",
  selected: "rgba(11,17,23,0.06)",
};

const dark = {
  bg: "#0a0d11",
  bgPane: "#11151a",
  bgSide: "#0c1014",
  bgElev: "#161b22",
  bgInput: "#11151a",
  ink: "#e6edf3",
  ink2: "#b1bac4",
  ink3: "#7d8590",
  ink4: "#484f58",
  line: "rgba(230,237,243,0.08)",
  line2: "rgba(230,237,243,0.16)",
  hover: "rgba(230,237,243,0.04)",
  selected: "rgba(230,237,243,0.07)",
};

export const palettes = {
  light: { ...light, ...status, accent },
  dark: { ...dark, ...status, accent },
};
