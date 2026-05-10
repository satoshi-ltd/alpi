// "default" is the physical name (~/.alpi/ root) but we surface it as
// "alpi" to match the product. Reserved at create-time too — see
// RESERVED_PROFILE_NAMES in alpi/host/config.py.
export const DEFAULT_PROFILE_DISPLAY = "alpi";
export const RESERVED_PROFILE_NAMES = ["default", "alpi"];

export function profileLabel(name) {
  return name === "default" ? DEFAULT_PROFILE_DISPLAY : name;
}
