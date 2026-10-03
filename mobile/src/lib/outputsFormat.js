import { stripPreviewMarkdown } from '../../../common/stripPreviewMarkdown.mjs';

export { stripPreviewMarkdown };

export function rowTitle(row) {
  const persisted = stripPreviewMarkdown(row?.title);
  if (persisted) return persisted;
  const line = row?.body?.split('\n').find((it) => stripPreviewMarkdown(it));
  return stripPreviewMarkdown(line) || '—';
}

export function severityTag(row) {
  const type = String(row?.type || '').toLowerCase();
  if (!type || type === 'info') return null;
  return type.toUpperCase();
}

export function openChatTarget(row, connectionId) {
  if (!row || !row.session_id) return null;
  const params = { id: row.profile, sid: row.session_id };
  if (connectionId) params.connectionId = connectionId;
  return { pathname: '/chat/[id]', params };
}

export function fmtRelative(ts, nowMs = Date.now()) {
  if (!ts) return '';
  const diff = nowMs / 1000 - ts;
  if (diff < 60) return 'now';
  if (diff < 3600) return `${Math.round(diff / 60)}m`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h`;
  if (diff < 86400 * 7) return `${Math.round(diff / 86400)}d`;
  return `${Math.round(diff / (86400 * 7))}w`;
}

export const REPLY_QUOTE_MAX = 1200;

export function replyDraft(row) {
  if (!row) return '';
  const title = stripPreviewMarkdown(row.title);
  const body = String(row.body ?? '').trim();
  const chars = Array.from(body);
  const clipped = chars.length > REPLY_QUOTE_MAX ? `${chars.slice(0, REPLY_QUOTE_MAX - 1).join('').trimEnd()}…` : body;
  const text = [title ? `**${title}**` : '', clipped].filter(Boolean).join('\n\n');
  if (!text) return '';
  return `${text.split('\n').map((line) => (line ? `> ${line}` : '>')).join('\n')}\n\n`;
}

export const clip = (text, max) => (text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text);
