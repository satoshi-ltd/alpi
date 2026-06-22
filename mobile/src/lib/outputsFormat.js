export function stripPreviewMarkdown(text) {
  return String(text || '')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/`{1,3}/g, '')
    .replace(/[*_~>#-]+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function rowTitle(row) {
  const persisted = stripPreviewMarkdown(row?.title);
  if (persisted) return persisted;
  const line = row?.body?.split('\n').find((it) => stripPreviewMarkdown(it));
  return stripPreviewMarkdown(line) || '—';
}
