import { mobile, space } from '../theme/tokens';

export const SIDEBAR_W = 320;
export const MIN_W = 700;
export const MIN_H = 500;
export const HYSTERESIS = 24;

export const CONTENT_MAX_W = 720;
// Desktop --pane-pad-x: header, transcript rows and composer share it; Bubble rows carry this same token, so the capped column adds none.
export const PANE_PAD_X = space.s7;
export const BUBBLE_MAX_PANE = '76%';

export const CHROME_H = mobile.tap;
export const CHROME_BTN = space.s10;
export const COMPOSER_PAD_Y = space.s3;
export const COMPOSER_CTRL = mobile.tap;
export const tapSlop = (size) => (mobile.tap - size) / 2;

// The height gate is what keeps every phone single-pane: no iPhone clears 500pt in landscape (17 Pro Max is 956x440).
export function isTwoPane(width, height) {
  return height >= MIN_H && width >= MIN_W;
}

export function nextTwoPane(prev, width, height) {
  if (height < MIN_H) return false;
  return prev ? width >= MIN_W - HYSTERESIS : width >= MIN_W;
}

export const SETTINGS_PATH = '/settings';
export const OUTPUTS_PATH = '/outputs';

const FULL_BLEED = ['/onboarding', '/pair', '/paired', '/biometric'];
// Shell destinations own the detail pane, so they are roots not drills
const PANE_ROOT_PATHS = ['/', SETTINGS_PATH, OUTPUTS_PATH];
const PANE_ROOT_KINDS = ['chat', 'wg'];
const SELECTION_KINDS = ['chat', 'wg', 'profile'];
const PROFILE_SECTIONS = ['brain/memory', 'brain/skills', 'brain/tools', 'email', 'mcp', 'peers', 'providers', 'schedule'];

function normalize(pathname) {
  const path = String(pathname || '').split('?')[0].split('#')[0].replace(/\/+$/, '');
  return path || '/';
}

function segments(pathname) {
  return normalize(pathname).split('/').filter(Boolean);
}

export function isFullBleed(pathname) {
  const path = normalize(pathname);
  if (FULL_BLEED.includes(path)) return true;
  return path === '/debug' || path.startsWith('/debug/');
}

export function isPaneRoot(pathname) {
  const path = normalize(pathname);
  if (PANE_ROOT_PATHS.includes(path)) return true;
  const parts = segments(path);
  return parts.length === 2 && PANE_ROOT_KINDS.includes(parts[0]);
}

export function sidebarSelection(pathname) {
  const [kind, id] = segments(pathname);
  if (!SELECTION_KINDS.includes(kind) || !id || id === 'new') return null;
  return { kind, id };
}

export function isHome(pathname) {
  return normalize(pathname) === '/';
}

export function subjectPath(item) {
  if (!item?.id) return null;
  return item.kind === 'workgroup' ? `/wg/${item.id}` : `/chat/${item.id}`;
}

function hasHistory(item) {
  return !!item?.id && item.sortKey > 0;
}

export function resumePath(items) {
  return subjectPath((items ?? []).find(hasHistory));
}

export function openVerb({ twoPane, pathname } = {}) {
  if (!twoPane) return 'push';
  return isPaneRoot(pathname) ? 'replace' : 'push';
}

export function backFallback(pathname) {
  const parts = segments(pathname);
  if (parts.length < 2 || isPaneRoot(pathname)) return '/';
  const [kind, id, ...rest] = parts;
  if (kind === 'outputs') return OUTPUTS_PATH;
  if (kind === 'wg') return `/wg/${id}`;
  if (kind !== 'profile') return '/';
  const section = rest.slice(0, -1).join('/');
  return PROFILE_SECTIONS.includes(section) ? `/profile/${id}/${section}` : `/chat/${id}`;
}

export function stackAnimation(twoPane) {
  return twoPane ? 'none' : 'slide_from_right';
}
