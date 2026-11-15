export const buttonVariants = ["primary", "secondary", "ghost", "danger", "danger-ghost"];

export const buttonHeights = {
  sm: { desktop: 32, mobile: 44 },
  md: { desktop: 40, mobile: 48 },
  lg: { desktop: 40, mobile: 48 },
  hero: { desktop: 48, mobile: 56 },
};

export const buttonDefaults = {
  desktop: { variant: "ghost", size: "md" },
  mobile: { variant: "primary", size: "lg" },
};

export const buttonRadius = "pill";

export const buttonLabelWeight = {
  primary: "medium",
  secondary: "medium",
  danger: "medium",
  ghost: "medium",
  "danger-ghost": "medium",
};

export const buttonHover = {
  primary: { from: "accent", amount: 0.86, toward: "pane" },
  secondary: { token: "hover" },
  ghost: { token: "hover" },
};

export const buttonPressed = {
  primary: { from: "accent", amount: 0.78, toward: "pane" },
  secondary: { token: "pressed" },
  danger: { from: "danger", amount: 0.76, toward: "black" },
  ghost: { token: "pressed" },
  "danger-ghost": { from: "danger", amount: 0.18, toward: "pane" },
};

export const buttonAccentPressed = { amount: 0.82, toward: "black" };

export const buttonStates = { disabled: "alpha", loading: "keepLabel", loadingFades: false };
