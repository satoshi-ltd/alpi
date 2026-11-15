export const BUSY_DELAY_MS = 300;
export const BUSY_MIN_MS = 400;
export const BUSY_CYCLE_S = 1.6;
export const BUSY_MIN_MARK_PX = 18;
export const BUSY_LABEL = "Loading";

export function busyPlan({ active, startedAt = null, shownAt = null }, now) {
  if (active) {
    if (shownAt != null) return { visible: true, wakeIn: null };
    const wait = BUSY_DELAY_MS - Math.max(0, now - (startedAt ?? now));
    return wait <= 0 ? { visible: true, wakeIn: null } : { visible: false, wakeIn: wait };
  }
  if (shownAt == null) return { visible: false, wakeIn: null };
  const left = BUSY_MIN_MS - Math.max(0, now - shownAt);
  return left > 0 ? { visible: true, wakeIn: left } : { visible: false, wakeIn: null };
}
