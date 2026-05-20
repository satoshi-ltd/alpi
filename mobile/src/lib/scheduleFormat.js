// Mirror of desktop util scheduleSummary — the raw daemon job exposes `kind`+ `expression`/`run_at`/`after_hours`, so we synthesize the same compact summary the desktop SchedulesSection renders.

export function scheduleSummary(j) {
  if (!j) return '?';
  if (j.kind === 'cron') return `cron ${j.expression || '?'}`;
  if (j.kind === 'once') return `once ${j.run_at || '?'}`;
  if (j.kind === 'inactivity') return `after ${j.after_hours ?? '?'}h`;
  return j.kind || '?';
}
