export const NOTIFIABLE_KINDS = [
  'wg.mention',
  'wg.done',
  'chat.turn_done',
  'approval.request',
  'schedule.done',
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
    case 'wg.mention':
      return {
        title: `${prefix} · mention`,
        body: data.summary || 'You were mentioned in a workgroup.',
      };
    case 'wg.done':
      return {
        title: `${prefix} · task done`,
        body: data.summary || 'A workgroup task was closed.',
      };
    case 'chat.turn_done': {
      const tools = Number.isFinite(data.tool_count) ? data.tool_count : 0;
      const dur = Number.isFinite(data.duration_s) ? data.duration_s : 0;
      const note = tools
        ? `${tools} tool${tools === 1 ? '' : 's'} · ${Math.round(dur)}s`
        : `${Math.round(dur)}s`;
      return {
        title: `${prefix} · reply ready`,
        body: data.summary ? `${data.summary} (${note})` : `Long-running turn finished (${note}).`,
      };
    }
    case 'approval.request':
      return {
        title: `${prefix} · approval needed`,
        body: data.command || 'Tool execution awaiting approval.',
      };
    case 'schedule.done':
      return {
        title: `${prefix} · schedule ok`,
        body: data.message || data.reply || 'Scheduled job completed.',
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
    case 'wg.mention':
    case 'wg.done':
      return data.wg_id ? `/wg/${data.wg_id}` : '/';
    case 'chat.turn_done':
      return data.session_id ? `/chat/${data.session_id}` : '/';
    case 'approval.request':
      return '/';
    case 'schedule.done':
    case 'schedule.failed':
      return data.profile ? `/profile/${data.profile}/schedule` : '/';
    case 'budget.threshold':
      return data.profile ? `/profile/${data.profile}` : '/';
    default:
      return '/';
  }
}
