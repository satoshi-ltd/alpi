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

export const typeLadder = {
  meta: 12,
  small: 14,
  ui: 15,
  read: 16,
  title: 20,
  display: 28,
};

export const typeFloor = typeLadder.meta;

export const typeLeading = {
  meta: 1.35,
  small: 1.45,
  ui: 1.4,
  read: 1.6,
  title: 1.25,
  display: 1.1,
};

export const monoScale = 0.92;

export const fontSizes = {
  xxs: typeLadder.meta,
  label: typeLadder.meta,
  xs: typeLadder.meta,
  sm: typeLadder.small,
  base: typeLadder.ui,
  md: typeLadder.ui,
  lg: typeLadder.read,
  xl: typeLadder.title,
  xxl: typeLadder.title,
  display: typeLadder.display,
};

export const lineHeights = {
  tight: 1,
  cozy: 1.3,
  normal: 1.5,
  relaxed: 1.6,
};

export const fontWeights = {
  regular: 400,
  medium: 500,
  semibold: 600,
};

export const eyebrow = { size: typeLadder.small, tracking: 0, family: "sans", weight: 500, ink: "ink3", case: "sentence" };

export const spaceScale = {
  4: 4,
  8: 8,
  12: 12,
  16: 16,
  24: 24,
  32: 32,
  48: 48,
};

export const controlHeight = {
  32: 32,
  40: 40,
  48: 48,
};

export const controlRole = { compact: 32, control: 40, touch: 48 };

export const touchTarget = { min: 44, control: 48 };

export const motionTokens = {
  fast: 120,
  enter: 180,
  exit: 130,
  pulse: 1600,
  pulseLow: 0.4,
  easeEnter: [0.2, 0.7, 0.2, 1],
  easeExit: [0.8, 0, 0.8, 0.3],
};

export const focusRing = { width: 2, offset: 2, alpha: 0.6 };

export const fieldFocus = { width: 1.5, ink: "ink3" };

export const iconStrokeRendered = 1.5;
export const iconViewBox = 24;
export const iconStrokeFor = (size) => (iconStrokeRendered * iconViewBox) / size;
export const iconSizes = { inline: 16, control: 20, nav: 24 };
export const iconSizesAllowed = { desktop: Object.values(iconSizes), mobile: Object.values(iconSizes) };

export const dotScale = { sm: 6, md: 8 };

export const space = {
  s1: 4,
  s2: 8,
  s3: 8,
  s4: 12,
  s5: 12,
  s6: 16,
  s7: 16,
  s8: 24,
  s9: 24,
  s10: 32,
  s11: 48,
};

export const spaceMicro = {
  hair: 1,
  tight: 2,
  snug: 3,
};

export const shell = {
  sidebar: 272,
  header: 56,
  stream: 760,
  composer: 56,
  rowDesktop: 40,
  rowPhone: 64,
  tile: 48,
};

export const radii = {
  xs: 6,
  control: 12,
  surface: 20,
  sheet: 28,
  pill: 999,
};

export const radiusRole = {
  xs: "checkbox, key cap, inline code",
  control: "fields you type in, list rows, menu items, the selection fill",
  surface: "cards, groups, bubbles, menus, toasts, approvals",
  sheet: "dialogs, sheets, the palette, the composer",
  pill: "everything you press: buttons, chips, selects, segments, switches, icon buttons",
};

export const retiredRadii = ["chip", "tag", "sm", "md", "lg", "xl", "2xl", "3xl"];

export const nestInset = 8;

export const stateFills = {
  light: { hover: 0.04, selected: 0.08, pressed: 0.12 },
  dark: { hover: 0.05, selected: 0.09, pressed: 0.13 },
};

export const stateFill = stateFills.light;

export const stateMotion = { enter: "fast", exit: "exit" };

export const floatShadow = {
  light: "0 12px 32px rgba(0, 0, 0, 0.10), 0 1px 3px rgba(0, 0, 0, 0.06)",
  dark: "0 0 0 1px rgba(237, 237, 237, 0.09), 0 16px 40px rgba(0, 0, 0, 0.55)",
};

export const veils = {
  light: "rgba(20, 20, 20, 0.22)",
  dark: "rgba(0, 0, 0, 0.55)",
};

export const bannerTint = {
  light: { tint: 0.1, quiet: 0.05 },
  dark: { tint: 0.14, quiet: 0.06 },
};

export const alpha = {
  faint: 0.35,
  disabled: 0.45,
  muted: 0.55,
  soft: 0.7,
};

export const glyphSize = 8;
export const glyphSizeMd = 14;

export const status = {
  success: "#3fb37a",
  warning: "#e08a3c",
  danger: "#c14545",
};

const light = {
  bg: "#ffffff",
  bgPane: "#ffffff",
  bgSide: "#f6f6f6",
  bgElev: "#ffffff",
  bgInput: "#f2f2f2",
  card: "#f2f2f2",
  field: "#f2f2f2",
  fill: "#f2f2f2",
  raised: "#ffffff",
  ink: "#141414",
  ink2: "#454545",
  ink3: "#6b6b6b",
  ink4: "#b4b4b4",
  edge: "#8c8c8c",
  focus: "rgba(20,20,20,0.6)",
  line: "rgba(20,20,20,0.07)",
  line2: "rgba(20,20,20,0.14)",
  hover: "rgba(20,20,20,0.04)",
  selected: "rgba(20,20,20,0.08)",
  pressed: "rgba(20,20,20,0.12)",
  accent: "#14110c",
  successText: "#217a45",
  warningText: "#b3470e",
  dangerText: "#b73737",
  onDanger: "#ffffff",
  markEye: "#ffffff",
};

const dark = {
  bg: "#1a1a1a",
  bgPane: "#1a1a1a",
  bgSide: "#121212",
  bgElev: "#2c2c2c",
  bgInput: "#262626",
  card: "#262626",
  field: "#262626",
  fill: "#262626",
  raised: "#2c2c2c",
  ink: "#ededed",
  ink2: "#b4b4b4",
  ink3: "#969696",
  ink4: "#4a4a4a",
  edge: "#7a7a7a",
  focus: "rgba(237,237,237,0.6)",
  line: "rgba(237,237,237,0.08)",
  line2: "rgba(237,237,237,0.16)",
  hover: "rgba(237,237,237,0.05)",
  selected: "rgba(237,237,237,0.09)",
  pressed: "rgba(237,237,237,0.13)",
  accent: "#f3efe6",
  successText: "#70c592",
  warningText: "#f59e5b",
  dangerText: "#f08080",
  onDanger: "#ffffff",
  markEye: "#000000",
};

export const surfaces = {
  light: { side: light.bgSide, pane: light.bgPane, fill: light.fill, raised: light.raised },
  dark: { side: dark.bgSide, pane: dark.bgPane, fill: dark.fill, raised: dark.raised },
};

export const ladderDirection = { light: "descends", dark: "ascends" };

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
