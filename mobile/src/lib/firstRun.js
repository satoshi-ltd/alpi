import { ALPACA_FOLD, FOLD_SIZES, foldFacets } from '../../../common/folds.mjs';
import { lineHeights, space, tracking } from '../theme/tokens';
import { isTwoPane } from './panes';

export const FIRST_RUN_MAX_W = 480;
export const FIRST_RUN_PATHS = ['/onboarding', '/pair', '/paired'];
export const BUSY_MARK_PX = 77;

export const firstRun = {
  top: space.s9,
  gap: space.s9,
  stack: space.s7,
  tight: space.s3,
  edge: space.s7,
  foldEdge: space.s9,
};

export const firstRunColumn = { width: '100%', maxWidth: FIRST_RUN_MAX_W, alignSelf: 'flex-start' };

const INK = foldFacets(ALPACA_FOLD).flatMap(({ points }) => points);
const INK_LEFT = Math.min(...INK.map(([x]) => x));
const INK_TOP = Math.min(...INK.map(([, y]) => y));

export const markInset = (px) => (INK_LEFT * px) / 100;

export const firstRunEdge = (width, height) => (isTwoPane(width, height) ? firstRun.foldEdge : firstRun.edge);

export const foldMarkStyle = { marginLeft: -markInset(FOLD_SIZES.hero), alignSelf: 'flex-start' };

export const busyMarkStyle = (() => {
  const top = (INK_TOP * BUSY_MARK_PX) / 100;
  return {
    padding: 0,
    gap: 0,
    alignItems: 'flex-start',
    justifyContent: 'flex-start',
    alignSelf: 'flex-start',
    marginLeft: -markInset(BUSY_MARK_PX),
    marginTop: -top,
    marginBottom: -(BUSY_MARK_PX - FOLD_SIZES.hero - top),
  };
})();

export const firstRunScroll = (insets, edge) => ({
  flexGrow: 1,
  paddingTop: insets.top + firstRun.top,
  paddingHorizontal: edge,
  paddingBottom: firstRun.stack,
});

export const firstRunBottom = (insets, edge, keyboardOpen = false) => ({
  paddingHorizontal: edge,
  paddingTop: firstRun.stack,
  paddingBottom: firstRun.stack + (keyboardOpen ? 0 : insets.bottom),
});

export const firstRunActions = { ...firstRunColumn, gap: firstRun.tight };

const lineOf = (size, ratio) => Math.round(size * ratio);

export function firstRunType({ colors, fonts, fontSizes }, titleSize = fontSizes.display) {
  return {
    title: {
      fontFamily: fonts.sans.semibold,
      fontSize: titleSize,
      lineHeight: lineOf(titleSize, lineHeights.cozy),
      letterSpacing: titleSize * tracking.tight,
      color: colors.ink,
      marginTop: firstRun.gap,
    },
    fact: {
      fontFamily: fonts.mono,
      fontSize: fontSizes.sm,
      lineHeight: lineOf(fontSizes.sm, lineHeights.cozy),
      color: colors.ink3,
      marginTop: firstRun.tight,
    },
    sentence: {
      fontFamily: fonts.sans.regular,
      fontSize: fontSizes.md,
      lineHeight: lineOf(fontSizes.md, lineHeights.normal),
      color: colors.ink2,
      marginTop: firstRun.tight,
    },
    sourceLabel: {
      fontFamily: fonts.sans.regular,
      fontSize: fontSizes.sm,
      lineHeight: lineOf(fontSizes.sm, lineHeights.cozy),
      color: colors.ink3,
    },
    sourcePath: {
      fontFamily: fonts.mono,
      fontSize: fontSizes.md,
      lineHeight: lineOf(fontSizes.md, lineHeights.normal),
      color: colors.ink2,
    },
    failureTitle: {
      fontFamily: fonts.sans.semibold,
      fontSize: fontSizes.lg,
      lineHeight: lineOf(fontSizes.lg, lineHeights.cozy),
      color: colors.dangerText,
    },
    failureHint: {
      fontFamily: fonts.sans.regular,
      fontSize: fontSizes.md,
      lineHeight: lineOf(fontSizes.md, lineHeights.normal),
      color: colors.ink2,
    },
  };
}
