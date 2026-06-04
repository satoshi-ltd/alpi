const CODE_EXT = new Set([
  'js', 'jsx', 'ts', 'tsx', 'py', 'go', 'rs', 'sh', 'sql',
  'json', 'yaml', 'yml', 'html', 'htm',
]);
const TEXT_EXT = new Set(['txt', 'text', 'log', 'md', 'markdown', 'csv']);

export function fileKind(name, mime) {
  if (String(mime || '').startsWith('image/')) return 'image';
  const ext = String(name || '').toLowerCase().split('.').pop();
  if (CODE_EXT.has(ext)) return 'code';
  if (TEXT_EXT.has(ext)) return 'text';
  if (mime === 'application/pdf') return 'file';
  if (String(mime || '').startsWith('text/')) return 'text';
  return 'file';
}

export function fileTypeLabel(name, mime) {
  const sub = String(mime || '').split('/').pop();
  if (sub) return sub;
  return String(name || '').toLowerCase().split('.').pop() || 'file';
}

export function fmtSize(n) {
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${n || 0} B`;
}
