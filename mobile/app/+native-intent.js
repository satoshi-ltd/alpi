const PAIRING_LINK = /^(?:alpi:\/\/)?\/?device\?/;
const INTERNAL_PARAMS = ['draft'];

function withoutInternalParams(raw) {
  const at = raw.indexOf('?');
  if (at < 0) return raw;
  const query = new URLSearchParams(raw.slice(at + 1));
  let changed = false;
  for (const key of INTERNAL_PARAMS) {
    if (query.has(key)) {
      query.delete(key);
      changed = true;
    }
  }
  if (!changed) return raw;
  const rest = query.toString();
  return rest ? `${raw.slice(0, at)}?${rest}` : raw.slice(0, at);
}

export function redirectSystemPath({ path }) {
  const raw = typeof path === 'string' ? path : '';
  if (!PAIRING_LINK.test(raw)) return typeof path === 'string' ? withoutInternalParams(path) : path;
  return `/pair${raw.slice(raw.indexOf('?'))}`;
}
