export const buttonVariants = ["primary", "secondary", "ghost", "danger", "danger-ghost"];

export const buttonHeights = {
  sm: { desktop: 28, mobile: 44 },
  md: { desktop: 32, mobile: 44 },
  lg: { desktop: 40, mobile: 48 },
  hero: { desktop: 48, mobile: 56 },
};

export const buttonDefaults = {
  desktop: { variant: "ghost", size: "md" },
  mobile: { variant: "primary", size: "lg" },
};

export const buttonLabelWeight = {
  primary: "semibold",
  secondary: "semibold",
  danger: "semibold",
  ghost: "medium",
  "danger-ghost": "medium",
};

export const buttonPressed = {
  primary: { from: "ink", amount: 0.85, toward: "pane" },
  secondary: { from: "ink", amount: 0.18, toward: "pane" },
  danger: { from: "danger", amount: 0.76, toward: "black" },
  ghost: { token: "line" },
  "danger-ghost": { from: "danger", amount: 0.18, toward: "pane" },
};

export const buttonAccentPressed = { amount: 0.82, toward: "black" };

export const buttonStates = { disabled: "alpha", loading: "keepLabel", loadingFades: false };
