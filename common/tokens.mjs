export const fontFamilies = {
  sans: "Geist",
  mono: "Geist Mono",
};

export const fontStacks = {
  sans: `"${fontFamilies.sans}", ui-sans-serif, system-ui, sans-serif`,
  mono: `"${fontFamilies.mono}", ui-monospace, SFMono-Regular, Menlo, monospace`,
};

// React Native resolves one family per weight; the name is the family without spaces.
export const nativeFace = (role, weight) =>
  `${fontFamilies[role].replace(/ /g, "")}_${weight}`;

export const fontSizes = {
  xxs: 9,
  // The uppercase mono label — table heads, field labels, audit rows. Named for its role,
  // not its rung; it sits between xxs and xs because that is where it measures.
  label: 10,
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

// Both apps extend the scale past s9 and picked different numbers — a desktop pane's
// padding is not a phone's. Declared here so the shared name collision is visible.
// Intra-component nudges below the layout rhythm: icon-to-label inside a control, stacked
// meta lines. The numbered scale starts at 4 and these are not steps of it.
export const spaceMicro = {
  hair: 1,
  tight: 2,
  snug: 3,
};

export const spaceExtra = {
  desktop: { s10: 32, s11: 40 },
  mobile: { s10: 28, s11: 36 },
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
  warning: "#e08a3c",
  danger: "#c14545",
};

const light = {
  bg: "#eef0f2",
  bgPane: "#ffffff",
  bgSide: "#f5f6f8",
  bgElev: "#ffffff",
  bgInput: "#ffffff",
  ink: "#0b1117",
  ink2: "#3d4955",
  ink3: "#626e7d",
  ink4: "#b1bac4",
  line: "rgba(11,17,23,0.07)",
  line2: "rgba(11,17,23,0.14)",
  hover: "rgba(11,17,23,0.04)",
  selected: "rgba(11,17,23,0.06)",
  accent: "#8a5a0a",
  successText: "#217a45",
  warningText: "#8a5a0a",
  dangerText: "#b73737",
  onDanger: "#ffffff",
};

const dark = {
  bg: "#0a0d11",
  bgPane: "#11151a",
  bgSide: "#0c1014",
  bgElev: "#161b22",
  bgInput: "#11151a",
  ink: "#e6edf3",
  ink2: "#b1bac4",
  ink3: "#828b97",
  ink4: "#484f58",
  line: "rgba(230,237,243,0.08)",
  line2: "rgba(230,237,243,0.16)",
  hover: "rgba(230,237,243,0.04)",
  selected: "rgba(230,237,243,0.07)",
  accent: "#f0b447",
  successText: "#70c592",
  warningText: "#efb254",
  dangerText: "#f08080",
  onDanger: "#ffffff",
};

export const palettes = {
  light: { ...light, ...status },
  dark: { ...dark, ...status },
};

export const typography = {
  chat: { size: "lg", leading: "relaxed" },
  dialogTitle: { size: "xl", leading: "cozy" },
  body: { size: "md", leading: "normal" },
  caption: { size: "sm", leading: "cozy" },
  metadata: { size: "xs", leading: "cozy" },
};
