export const NOTIFIABLE_KINDS = [
  'agent.message',
  'wg.done',
  'approval.request',
  'schedule.failed',
  'budget.threshold',
];


// Only approval.request expires: the daemon auto-denies at its own deadline, and a banner for an already-decided request is worse than silence.
export function isStale(event, nowMs) {
  if (event?.event !== 'approval.request') return false;
  const data = event?.data || {};
  const ts = Number(data.ts);
  const timeout = Number(data.timeout_s);
  if (!Number.isFinite(ts) || !Number.isFinite(timeout) || timeout <= 0) return false;
  return Number(nowMs) > (ts + timeout) * 1000;
}


export function formatNotification(event, connection) {
  const kind = event?.event;
  const data = event?.data || {};
  const conn = connection?.name || 'alpi';
  const profile = data.profile || '';
  const prefix = profile ? `${conn} · ${profile}` : conn;
  switch (kind) {
    case 'agent.message': {
      const tag = data.type && data.type !== 'info' ? ` · ${data.type}` : '';
      return {
        title: `${data.title || prefix}${tag}`,
        body: data.body || 'New message from your agent.',
      };
    }
    case 'wg.done':
      return {
        title: `${prefix} · task done`,
        body: data.summary || 'A workgroup task was closed.',
      };
    case 'approval.request':
      return {
        title: `${prefix} · approval needed`,
        body: data.command || 'Tool execution awaiting approval.',
      };
    case 'schedule.failed': {
      const name = data.title || data.job_id || '';
      const reason = (data.body || data.message || '').replace(/\n+/g, ' · ');
      const detail = reason ? (name ? `${name}: ${reason}` : reason) : name;
      return {
        title: `${prefix} · schedule failed`,
        body: detail || 'Scheduled job failed.',
      };
    }
    case 'budget.threshold':
      return {
        title: `${prefix} · budget ${data.level || ''}%`,
        body: 'Daily budget threshold reached.',
      };
    default:
      return { title: prefix, body: kind || 'Event' };
  }
}


export function deepLinkFor(event, _connection) {
  const kind = event?.event;
  const data = event?.data || {};
  switch (kind) {
    case 'agent.message':
      if (typeof data.deep_link === 'string' && data.deep_link) {
        return data.deep_link;
      }
      return data.profile ? `/chat/${data.profile}` : '/';
    case 'wg.done':
      return data.wg_id ? `/wg/${data.wg_id}` : '/';
    case 'approval.request':
      return '/';
    case 'schedule.failed':
      if (typeof data.deep_link === 'string' && data.deep_link) {
        return data.deep_link;
      }
      return data.profile ? `/profile/${data.profile}/schedule` : '/';
    case 'budget.threshold':
      return data.profile ? `/profile/${data.profile}/settings` : '/';
    default:
      return '/';
  }
}
