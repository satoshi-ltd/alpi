export { scheduleSummary } from "../../../common/schedule.mjs";

import { formatRelative } from './format';



export function formatLastRun(iso, status) {
  if (status === 'error' && !iso) return 'last run failed';
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
  return job?.last_run_status === 'error';
}

export function jobTitle(job) {
  return job?.title?.trim() || job?.prompt?.trim().split('\n')[0] || `job ${String(job?.id ?? '').slice(0, 6)}`;
}


const pad = (n) => String(n).padStart(2, '0');
const startOfDay = (ms) => {
  const d = new Date(ms);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
};

export function clockOf(sec) {
  const d = new Date(sec * 1000);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function dayLabel(sec, nowSec) {
  const days = Math.round((startOfDay(sec * 1000) - startOfDay(nowSec * 1000)) / 86400000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Tomorrow';
  const d = new Date(sec * 1000);
  return `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
}


const oneLine = (text) => String(text ?? '').replace(/\s+/g, ' ').trim();

export function lastResultLine(job, startedClock = null) {
  if (startedClock) return `started ${startedClock}`;
  if (job?.last_run_status !== 'error') return formatLastRun(job?.last_run_at, job?.last_run_status);
  const ms = Date.parse(job.last_run_at ?? '');
  const rel = Number.isNaN(ms) ? '' : formatRelative(ms / 1000);
  const message = oneLine(job.last_run_message);
  return `${['failed', rel].filter(Boolean).join(' ')}${message ? ` · ${message}` : ''}`;
}

export function jobMatches(job, query, whenText = '') {
  const needle = oneLine(query).toLowerCase();
  if (!needle) return true;
  return [jobTitle(job), job.description, job.prompt, job.expression, job.id, whenText]
    .some((field) => String(field ?? '').toLowerCase().includes(needle));
}
