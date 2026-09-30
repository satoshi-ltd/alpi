import { iconSizes, lineHeights, mobile, space } from '../../theme/tokens';

export const PROCESS_ROW_H = 20;
export const PROCESS_GAP = space.s1;
export const TURN_GAP = space.s5;
export const PROCESS_LEAD_W = iconSizes.xs;
export const PROCESS_LEAD_GAP = space.s3;
export const PROCESS_INDENT = PROCESS_LEAD_W + PROCESS_LEAD_GAP;

export const PROCESS_EDGE = (mobile.tap - PROCESS_ROW_H) / 2;

// rows sit PROCESS_GAP apart, so inner slop may only meet the neighbour's, never overlap it
export function processSlop({ top = false, bottom = false } = {}) {
  const inner = PROCESS_GAP / 2;
  return { top: top ? PROCESS_EDGE : inner, bottom: bottom ? PROCESS_EDGE : inner, left: 0, right: 0 };
}

export const processRowStyle = {
  flexDirection: 'row',
  alignItems: 'center',
  gap: PROCESS_LEAD_GAP,
  minHeight: PROCESS_ROW_H,
};

export function processText({ fonts, fontSizes }, color) {
  return {
    fontFamily: fonts.mono,
    fontSize: fontSizes.sm,
    lineHeight: fontSizes.sm * lineHeights.cozy,
    color,
    includeFontPadding: false,
  };
}
