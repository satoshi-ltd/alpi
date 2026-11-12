export const BADGE_CAP = 9;

export const countBadgeSpec = { family: 'mono', weight: 600, size: { desktop: 14, mobile: 18 } };

export function badgeCount(n) {
  return n > BADGE_CAP ? `${BADGE_CAP}+` : String(n);
}
