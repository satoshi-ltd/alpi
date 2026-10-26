import { dotScale } from '../theme/tokens';

export function dotShape(size) {
  const px = dotScale[size];
  return { width: px, height: px, borderRadius: px / 2 };
}
