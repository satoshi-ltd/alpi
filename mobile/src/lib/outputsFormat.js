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
