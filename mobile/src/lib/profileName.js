export const DEFAULT_PROFILE_DISPLAY = 'alpi';

export const RESERVED_PROFILE_NAMES = ['default', 'alpi'];

export const PROFILE_NAME_RE = /^[a-z0-9][a-z0-9._-]*$/;

const MOBILE_ROUTE_CONFLICTS = ['new'];

export function profileLabel(name) {
  return name === 'default' ? DEFAULT_PROFILE_DISPLAY : name;
}

export function isValidProfileName(name) {
  return typeof name === 'string' && PROFILE_NAME_RE.test(name) && !name.includes('..');
}

export function profileNameError(trimmed, takenNames = []) {
  if (!trimmed) return null;
  if (!isValidProfileName(trimmed)) {
    return 'a–z, 0–9, ".", "_", "-"; must start with a letter or digit and never contain ".."';
  }
  if (RESERVED_PROFILE_NAMES.includes(trimmed)) {
    return `${trimmed} is reserved`;
  }
  if (MOBILE_ROUTE_CONFLICTS.includes(trimmed)) {
    return `${trimmed} clashes with an app route — pick another name`;
  }
  if (takenNames.includes(trimmed)) {
    return `@${trimmed} already exists`;
  }
  return null;
}
