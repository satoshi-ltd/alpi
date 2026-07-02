// Mirror of desktop util scheduleSummary — the raw daemon job exposes `kind`+ `expression`/`run_at`/`after_hours`, so we synthesize the same compact summary the desktop SchedulesSection renders.

import { formatRelative } from './format';

export function scheduleSummary(j) {
  if (!j) return '?';
  if (j.kind === 'cron') return j.expression || '?';
  if (j.kind === 'once') return `once ${j.run_at || '?'}`;
  if (j.kind === 'inactivity') return `after ${j.after_hours ?? '?'}h`;
  return j.kind || '?';
}

export function formatLastRun(iso, status) {
  if (!status || !iso) return 'never run';
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return 'never run';
  const rel = formatRelative(ms / 1000);
  return status === 'error' ? `last run failed · ${rel}` : `ran ${rel}`;
}
