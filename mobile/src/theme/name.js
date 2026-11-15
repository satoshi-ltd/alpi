import { nameTone } from '../../../common/name.mjs';
import { fonts } from './tokens';

export const NAME_MAX_FONT_SCALE = 2;
export const NAME_MIN_FIT = 24 / 28;

export function nameColor(accent, colors) {
  return nameTone(accent, colors.bg) ?? colors.ink;
}

export function nameSize(base, fontScale = 1) {
  return Math.round(base * Math.min(fontScale || 1, NAME_MAX_FONT_SCALE));
}

export function nameStyle(size, color) {
  return { fontFamily: fonts.name, fontSize: size, letterSpacing: -0.04 * size, lineHeight: Math.round(size * 1.2), color };
}

export const NAME_TEXT = { allowFontScaling: false, adjustsFontSizeToFit: true, minimumFontScale: NAME_MIN_FIT, numberOfLines: 1, accessibilityRole: 'header' };
