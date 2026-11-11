import { NO_PROSE } from '../../../../common/notificationParts.mjs';
import { deriveSummary, legacyTitle, notificationTitle } from '../../../../common/notificationSummary.mjs';
import { profileLabel } from '../../lib/profileName';

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


const LEVEL_WORD = { warning: 'Warning', error: 'Failed' };

// The daemon sends the profile name as the title when the row has none, so that value means "untitled".
export function agentMessageLines(data) {
  const profile = String(data?.profile || '').trim();
  const handle = profile ? `@${profileLabel(profile)}` : '';
  const raw = String(data?.title || '').trim();
  const title = raw === profile ? '' : typeof data?.summary === 'string' ? notificationTitle(raw) : legacyTitle(raw);
  const body = typeof data?.body === 'string' ? data.body : '';
  const text = String(data?.summary || '').trim() || deriveSummary(body) || (body.trim() ? NO_PROSE : '');
  const word = LEVEL_WORD[data?.type];
  return {
    title: [handle, title].filter(Boolean).join(' · ') || 'alpi',
    body: text ? (word ? `${word} · ${text}` : text) : 'New message from your agent.',
  };
}

export function formatNotification(event, connection) {
  const kind = event?.event;
  const data = event?.data || {};
  const conn = connection?.name || 'alpi';
  const profile = data.profile || '';
  const prefix = profile ? `${conn} · ${profile}` : conn;
  switch (kind) {
    case 'agent.message':
      return agentMessageLines(data);
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


const SEGMENT = "[A-Za-z0-9_][A-Za-z0-9._~%-]{0,255}";
// Only these in-app pages may be opened from a daemon's link: no scheme, host, query or dot segment.
const INTERNAL_ROUTES = [
  new RegExp(`^/outputs/${SEGMENT}/${SEGMENT}$`),
  new RegExp(`^/chat/${SEGMENT}$`),
  new RegExp(`^/wg/${SEGMENT}$`),
  new RegExp(`^/profile/${SEGMENT}/(settings|schedule)$`),
  new RegExp(`^/profile/${SEGMENT}/schedule/${SEGMENT}$`),
  /^\/(outputs|activity)?$/,
];

export function internalLink(link, fallback = '/') {
  if (typeof link !== 'string') return fallback;
  return INTERNAL_ROUTES.some((route) => route.test(link)) ? link : fallback;
}

export function deepLinkFor(event, _connection) {
  const kind = event?.event;
  const data = event?.data || {};
  switch (kind) {
    case 'agent.message': {
      const fallback = data.profile ? internalLink(`/chat/${data.profile}`) : '/';
      return data.deep_link ? internalLink(data.deep_link, fallback) : fallback;
    }
    case 'wg.done':
      return data.wg_id ? internalLink(`/wg/${data.wg_id}`) : '/';
    case 'approval.request':
    case 'clarification.request':
      return '/';
    case 'schedule.failed': {
      let fallback = '/';
      if (data.profile) {
        const schedule = internalLink(`/profile/${data.profile}/schedule`);
        fallback = data.job_id
          ? internalLink(`/profile/${data.profile}/schedule/${encodeURIComponent(data.job_id)}`, schedule)
          : schedule;
      }
      return data.deep_link ? internalLink(data.deep_link, fallback) : fallback;
    }
    case 'budget.threshold':
      return data.profile ? internalLink(`/profile/${data.profile}/settings`) : '/';
    default:
      return '/';
  }
}
