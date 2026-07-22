// Keep expo imports out of this module — it must stay unit-testable.

// 20 MiB base64 over a slow hop outlives the default RPC window.
export const FETCH_TIMEOUT_MS = 60_000;

const MIME_BY_EXT = {
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  webp: 'image/webp',
  pdf: 'application/pdf',
  txt: 'text/plain',
  text: 'text/plain',
  log: 'text/plain',
  md: 'text/markdown',
  markdown: 'text/markdown',
  csv: 'text/csv',
  json: 'application/json',
  yaml: 'application/yaml',
  yml: 'application/yaml',
  html: 'text/html',
  htm: 'text/html',
  js: 'text/plain',
  jsx: 'text/plain',
  ts: 'text/plain',
  tsx: 'text/plain',
  py: 'text/plain',
  go: 'text/plain',
  rs: 'text/plain',
  sh: 'text/plain',
  sql: 'text/plain',
};

export const ALLOWED_MIMES = new Set(Object.values(MIME_BY_EXT));

export function mimeFor(name, fallback = '') {
  const ext = String(name || '').toLowerCase().split('.').pop();
  return MIME_BY_EXT[ext] || fallback;
}

export function imageCacheKey(endpointId, profile, path) {
  return `${endpointId || ''}:${profile || ''}:${path || ''}`;
}

// Must stay in sync with alpi/attachments.py MAX_FILE_BYTES / MAX_TEXT_FILE_BYTES / TEXT_MIMES.
export const MAX_FILE_BYTES = 20 * 1024 * 1024;
export const MAX_TEXT_FILE_BYTES = 2 * 1024 * 1024;
const TEXT_MIMES = new Set([
  'text/plain', 'text/markdown', 'text/csv',
  'application/json', 'text/html',
  'application/yaml', 'text/yaml', 'application/x-yaml', 'text/x-yaml',
]);

export function attachmentByteCap(mime) {
  return TEXT_MIMES.has(mime) ? MAX_TEXT_FILE_BYTES : MAX_FILE_BYTES;
}

export function resolveAttachmentMime(name, mime) {
  return mime && ALLOWED_MIMES.has(mime)
    ? mime
    : mimeFor(name, 'application/octet-stream');
}

export function oversizeError(name, mime, bytes) {
  const cap = attachmentByteCap(mime);
  if (bytes > cap) {
    return `${name} is too large (${Math.round(cap / (1024 * 1024))} MB max)`;
  }
  return null;
}

function base64ByteLength(b64) {
  const s = String(b64 || '');
  const pad = s.endsWith('==') ? 2 : s.endsWith('=') ? 1 : 0;
  return Math.floor(s.length / 4) * 3 - pad;
}

export async function stageAttachment(call, { profile, name, mime, base64, size }) {
  const resolvedMime = resolveAttachmentMime(name, mime);
  const bytes = Number.isFinite(size) && size > 0
    ? size
    : base64ByteLength(base64);
  const err = oversizeError(name, resolvedMime, bytes);
  if (err) throw new Error(err);
  let res;
  try {
    res = await call('host.attachments.stage', {
      profile,
      name,
      mime: resolvedMime,
      data_base64: base64,
    }, { timeoutMs: FETCH_TIMEOUT_MS });
  } catch (e) {
    throw new Error(`could not upload ${name}: ${e?.message || e}`);
  }
  if (!res?.ok || !res?.attachment?.path) {
    throw new Error(`could not upload ${name}`);
  }
  return res.attachment;
}
