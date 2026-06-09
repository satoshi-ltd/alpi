export const DEFAULT_PROFILE_DISPLAY = "alpi";
export const RESERVED_PROFILE_NAMES = ["default", "alpi"];

export function profileLabel(name) {
  return name === "default" ? DEFAULT_PROFILE_DISPLAY : name;
}
