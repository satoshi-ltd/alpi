import { iconSizes, mobile, radii, space } from '../theme/tokens';
import { SHEET_CLOSE_BLEED } from './SheetClose';

export const sheetStyles = {
  dialog: {
    alignSelf: 'center',
    width: '100%',
    maxWidth: 560,
    borderRadius: radii.sheet,
  },
  dialogHeader: { paddingTop: space.s7 },
  grabberWrap: { alignItems: 'center', paddingTop: space.s3 },
  grabber: { width: 36, height: 4, borderRadius: radii.pill, opacity: 0.6 },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingLeft: space.s7,
    paddingRight: space.s7 + SHEET_CLOSE_BLEED - (mobile.tap - iconSizes.md) / 2,
    paddingTop: space.s5,
    paddingBottom: space.s6,
    gap: space.s5,
  },
};

export const POPOVER_W = 280;
export const POPOVER_GAP = space.s2;
export const POPOVER_EDGE = space.s3;

export function popoverPosition(anchor, windowWidth, windowHeight = Infinity, listMaxHeight = 0, bottomInset = 0) {
  const left = anchor.x + anchor.width - POPOVER_W;
  const maxTop = Math.max(POPOVER_EDGE, windowHeight - listMaxHeight - POPOVER_EDGE - bottomInset);
  return {
    top: Math.min(anchor.y + anchor.height + POPOVER_GAP, maxTop),
    left: Math.min(Math.max(left, POPOVER_EDGE), Math.max(POPOVER_EDGE, windowWidth - POPOVER_W - POPOVER_EDGE)),
  };
}
