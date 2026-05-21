import { NOTIFIABLE_KINDS } from './kinds';

const FIXTURES = {
  'wg.mention': {
    profile: 'vera',
    wg_id: 'wg-debug',
    seq: 999,
    from: 'peer-debug',
    summary: '@vera could you review the Q2 plan before tomorrow?',
  },
  'wg.done': {
    profile: 'vera',
    wg_id: 'wg-debug',
    seq: 998,
    summary: 'Task closed: shortlist of 5 vendors with notes.',
  },
  'chat.turn_done': {
    profile: 'vera',
    session_id: 'sess-debug',
    source: 'user',
    duration_s: 187.3,
    tool_count: 12,
    summary: 'Research complete: 5 vendors ranked by price, SLA, integration cost.',
  },
  'approval.request': {
    profile: 'vera',
    request_id: 'req-debug',
    command: 'rm -rf ./build',
    pattern: 'recursive rm',
    severity: 'caution',
    timeout_s: 60,
  },
  'schedule.done': {
    profile: 'vera',
    job_id: 'job-debug',
    kind: 'cron',
    message: 'Morning briefing delivered.',
    reply: 'Inbox cleaned, 3 priorities flagged.',
  },
  'schedule.failed': {
    profile: 'vera',
    job_id: 'job-debug',
    kind: 'cron',
    message: 'Morning briefing failed: upstream model timeout.',
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
