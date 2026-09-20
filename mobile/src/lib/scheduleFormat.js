export { scheduleSummary } from "../../../common/schedule.mjs";

import { formatRelative } from './format';



export function formatLastRun(iso, status) {
  if (!status || !iso) return 'never run';
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return 'never run';
  const rel = formatRelative(ms / 1000);
  return status === 'error' ? `last run failed · ${rel}` : `ran ${rel}`;
}
