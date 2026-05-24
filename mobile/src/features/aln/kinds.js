export const NOTIFIABLE_KINDS = [
  'agent.message',
  'wg.done',
  'approval.request',
  'schedule.failed',
  'budget.threshold',
];


export function formatNotification(event, connection) {
  const kind = event?.event;
  const data = event?.data || {};
  const conn = connection?.name || 'alpi';
  const profile = data.profile || '';
  const prefix = profile ? `${conn} · ${profile}` : conn;
  switch (kind) {
    case 'agent.message': {
      const sev = data.severity && data.severity !== 'normal' ? ` · ${data.severity}` : '';
      return {
        title: data.title || `${prefix}${sev}`,
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
    case 'schedule.failed':
      return {
        title: `${prefix} · schedule failed`,
        body: data.message || 'Scheduled job failed.',
      };
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
      return data.profile ? `/profile/${data.profile}/schedule` : '/';
    case 'budget.threshold':
      return data.profile ? `/profile/${data.profile}` : '/';
    default:
      return '/';
  }
}
