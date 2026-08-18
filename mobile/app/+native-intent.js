const PAIRING_LINK = /^(?:alpi:\/\/)?\/?device\?/;

export function redirectSystemPath({ path }) {
  const raw = typeof path === 'string' ? path : '';
  if (!PAIRING_LINK.test(raw)) return path;
  return `/pair${raw.slice(raw.indexOf('?'))}`;
}
