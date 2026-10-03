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
  tag: 2,
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
  bg: "#f0f0f0",
  bgPane: "#ffffff",
  bgSide: "#f6f6f6",
  bgElev: "#ffffff",
  bgInput: "#ffffff",
  ink: "#141414",
  ink2: "#454545",
  ink3: "#6b6b6b",
  ink4: "#b4b4b4",
  line: "rgba(20,20,20,0.07)",
  line2: "rgba(20,20,20,0.14)",
  hover: "rgba(20,20,20,0.04)",
  selected: "rgba(20,20,20,0.06)",
  accent: "#14110c",
  successText: "#217a45",
  warningText: "#b3470e",
  dangerText: "#b73737",
  onDanger: "#ffffff",
};

const dark = {
  bg: "#0b0b0b",
  bgPane: "#151515",
  bgSide: "#0f0f0f",
  bgElev: "#1b1b1b",
  bgInput: "#151515",
  ink: "#ededed",
  ink2: "#b4b4b4",
  ink3: "#8a8a8a",
  ink4: "#4a4a4a",
  line: "rgba(237,237,237,0.08)",
  line2: "rgba(237,237,237,0.16)",
  hover: "rgba(237,237,237,0.04)",
  selected: "rgba(237,237,237,0.07)",
  accent: "#f3efe6",
  successText: "#70c592",
  warningText: "#f59e5b",
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
