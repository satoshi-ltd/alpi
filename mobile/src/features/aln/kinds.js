export const NOTIFIABLE_KINDS = [
  'agent.message',
  'wg.done',
  'approval.request',
  'clarification.request',
  'schedule.failed',
  'budget.threshold',
];

// Polled beside the notifiable kinds only to refresh the inbox of a connection whose stream is not open; never a banner.
export const INBOX_KINDS = ['output.created', 'output.updated'];

export const POLL_KINDS = [...NOTIFIABLE_KINDS, ...INBOX_KINDS];


export const APPROVAL_CATEGORY = 'alpi.approval';
export const APPROVAL_ACTIONS = { deny: 'deny', allow_once: 'once' };

const REQUEST_KINDS = { 'approval.request': 'approval', 'clarification.request': 'clarification' };

export function requestDomain(kind) {
  return REQUEST_KINDS[kind] ?? null;
}

export function categoryFor(event) {
  return event?.event === 'approval.request' ? APPROVAL_CATEGORY : null;
}

// Only requests expire: the daemon auto-resolves at its own deadline, and a banner for an already-decided request is worse than silence.
export function isStale(event, nowMs) {
  if (!requestDomain(event?.event)) return false;
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
    case 'clarification.request':
      return {
        title: `${prefix} · question`,
        body: data.question || 'Your agent is waiting for an answer.',
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
    case 'clarification.request':
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
