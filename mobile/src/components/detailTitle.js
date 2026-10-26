import { lineHeights, tracking } from '../theme/tokens';

export function detailTitleStyle({ colors, fonts, fontSizes }, family = fonts.sans.semibold) {
  return {
    fontFamily: family,
    fontSize: fontSizes.xxl,
    lineHeight: fontSizes.xxl * lineHeights.cozy,
    letterSpacing: fontSizes.xxl * tracking.tight,
    color: colors.ink,
  };
}
