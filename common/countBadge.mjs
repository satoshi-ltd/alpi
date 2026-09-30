export const BADGE_CAP = 9;

export function badgeCount(n) {
  return n > BADGE_CAP ? `${BADGE_CAP}+` : String(n);
}
