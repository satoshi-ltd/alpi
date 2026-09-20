import { radii, space } from '../theme/tokens';

export const sheetStyles = {
  dialog: {
    alignSelf: 'center',
    width: '100%',
    maxWidth: 560,
    borderBottomLeftRadius: radii.sheet,
    borderBottomRightRadius: radii.sheet,
  },
  grabberWrap: { alignItems: 'center', paddingTop: space.s3 },
  grabber: { width: 36, height: 4, borderRadius: 2, opacity: 0.6 },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingLeft: space.s8,
    paddingRight: space.s5,
    paddingTop: space.s5,
    paddingBottom: space.s6,
    gap: space.s5,
  },
};
