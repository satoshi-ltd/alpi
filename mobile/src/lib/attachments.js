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

export async function stageAttachment(call, { profile, name, mime, base64 }) {
  const resolvedMime = mime && ALLOWED_MIMES.has(mime)
    ? mime
    : mimeFor(name, 'application/octet-stream');
  let res;
  try {
    res = await call('host.attachments.stage', {
      profile,
      name,
      mime: resolvedMime,
      data_base64: base64,
    });
  } catch (e) {
    throw new Error(`could not upload ${name}: ${e?.message || e}`);
  }
  if (!res?.ok || !res?.attachment?.path) {
    throw new Error(`could not upload ${name}`);
  }
  return res.attachment;
}
