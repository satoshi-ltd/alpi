export function normalizeEndpointUrl(value) {
  let parsed;
  try {
    parsed = new URL(String(value || '').trim());
  } catch {
    throw new Error('Endpoint must be a complete ws:// or wss:// URL');
  }
  if (parsed.protocol !== 'ws:' && parsed.protocol !== 'wss:') {
    throw new Error('Endpoint must use ws:// or wss://');
  }
  if (!parsed.hostname || parsed.username || parsed.password) {
    throw new Error('Endpoint cannot contain credentials');
  }
  if ((parsed.pathname && parsed.pathname !== '/') || parsed.search || parsed.hash) {
    throw new Error('Endpoint cannot contain a path, query, or fragment');
  }
  return `${parsed.protocol}//${parsed.host}`;
}

export function endpointUrl(endpoint) {
  if (endpoint?.url) return normalizeEndpointUrl(endpoint.url);
  if (endpoint?.ip && endpoint?.port) {
    return normalizeEndpointUrl(`ws://${endpoint.ip}:${endpoint.port}`);
  }
  return '';
}

export function endpointHost(endpoint) {
  try {
    return endpointUrl(endpoint);
  } catch {
    return '';
  }
}
