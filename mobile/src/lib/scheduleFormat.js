export { scheduleSummary } from "../../../common/schedule.mjs";

import { formatRelative } from './format';



export function formatLastRun(iso, status) {
  if (!status || !iso) return 'never run';
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return 'never run';
  const rel = formatRelative(ms / 1000);
  return status === 'error' ? `last run failed · ${rel}` : `ran ${rel}`;
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function formatNextFire(iso) {
  const ms = Date.parse(iso ?? '');
  if (Number.isNaN(ms)) return null;
  const d = new Date(ms);
  return `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]} at ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function jobFailed(job) {
  return job?.last_run_status === 'error' && !!job?.last_run_at;
}

export function jobTitle(job) {
  return job?.title?.trim() || job?.prompt?.trim().split('\n')[0] || `job ${String(job?.id ?? '').slice(0, 6)}`;
}
