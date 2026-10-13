import { notificationParts } from '../../../common/notificationParts.mjs';

export function openChatTarget(row, connectionId) {
  if (!row || !row.session_id) return null;
  const params = { id: row.profile, sid: row.session_id };
  if (connectionId) params.connectionId = connectionId;
  return { pathname: '/chat/[id]', params };
}

export const REPLY_QUOTE_MAX = 1200;

export function replyDraft(row) {
  if (!row) return '';
  const { title, givenSummary } = notificationParts(row);
  const body = [givenSummary, String(row.body ?? '').trim()].filter(Boolean).join('\n\n');
  const chars = Array.from(body);
  const clipped = chars.length > REPLY_QUOTE_MAX ? `${chars.slice(0, REPLY_QUOTE_MAX - 1).join('').trimEnd()}…` : body;
  const text = [title ? `**${title}**` : '', clipped].filter(Boolean).join('\n\n');
  if (!text) return '';
  return `${text.split('\n').map((line) => (line ? `> ${line}` : '>')).join('\n')}\n\n`;
}

export const clip = (text, max) => (text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text);
