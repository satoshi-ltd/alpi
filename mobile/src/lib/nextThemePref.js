export const THEME_ORDER = ['system', 'light', 'dark'];

export function nextThemePref(pref) {
  return THEME_ORDER[(THEME_ORDER.indexOf(pref) + 1) % THEME_ORDER.length];
}
