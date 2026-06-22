export const DEFAULT_PROFILE_DISPLAY = "alpi";
export const RESERVED_PROFILE_NAMES = ["default", "alpi"];
export const PROFILE_NAME_RE = /^[a-z0-9][a-z0-9._-]*$/;

export function isValidProfileName(name) {
  return typeof name === "string" && PROFILE_NAME_RE.test(name) && !name.includes("..");
}

export function profileLabel(name) {
  return name === "default" ? DEFAULT_PROFILE_DISPLAY : name;
}
