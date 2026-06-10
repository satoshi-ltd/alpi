import { NOTIFIABLE_KINDS } from './kinds';

const FIXTURES = {
  'agent.message': {
    profile: 'abby',
    title: 'Meeting in 10 min',
    body: 'Standup with the design team at 10:30.',
    type: 'warning',
    output_id: 'sample-output-id',
    deep_link: '/outputs/abby/sample-output-id',
  },
  'wg.done': {
    profile: 'vera',
    wg_id: 'wg-debug',
    seq: 998,
    summary: 'Task closed: shortlist of 5 vendors with notes.',
  },
  'approval.request': {
    profile: 'vera',
    request_id: 'req-debug',
    command: 'rm -rf ./build',
    pattern: 'recursive rm',
    severity: 'caution',
    timeout_s: 60,
  },
  'schedule.failed': {
    profile: 'vera',
    job_id: 'job-debug',
    kind: 'cron',
    message: 'Morning briefing failed: upstream model timeout.',
    output_id: 'sample-fail-id',
    deep_link: '/outputs/vera/sample-fail-id',
  },
  'budget.threshold': {
    profile: 'vera',
    level: '80',
    used_usd: 4.05,
    daily_usd: 5.0,
  },
};

export function sampleEvent(kind, { seqOffset = 0 } = {}) {
  if (!NOTIFIABLE_KINDS.includes(kind)) return null;
  const data = FIXTURES[kind] || {};
  return {
    event: kind,
    seq: 10_000 + seqOffset,
    at: Date.now() / 1000,
    data: { ...data },
  };
}

export const SAMPLE_KINDS = NOTIFIABLE_KINDS.slice();
