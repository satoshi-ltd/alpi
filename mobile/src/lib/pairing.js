import { normalizeEndpointUrl } from './endpoint.js';

export class PairingError extends Error {}

export function parsePairing(text) {
  const raw = (text ?? '').trim();
  if (!raw) throw new PairingError('Empty pairing input');

  if (raw.startsWith('alpi://')) return parseUri(raw);
  try {
    return parseJson(JSON.parse(raw));
  } catch (e) {
    if (e instanceof PairingError) throw e;
    throw new PairingError('Unrecognised pairing payload — paste an alpi:// link or pairing JSON');
  }
}

function parseUri(uri) {
  let params;
  try {
    params = new URL(uri).searchParams;
  } catch {
    throw new PairingError('alpi:// link is malformed');
  }
  const legacyHost = params.get('host');
  const legacyPort = Number(params.get('port'));
  const token = params.get('token');
  const candidate = params.get('url') || (legacyHost && legacyPort ? `ws://${legacyHost}:${legacyPort}` : '');
  if (!candidate || !token) {
    throw new PairingError('alpi:// link missing URL or token');
  }
  try {
    const url = normalizeEndpointUrl(candidate);
    const name = params.get('name') ?? new URL(url).hostname;
    const connectionId = params.get('connection_id') || params.get('c') || '';
    return {
      name, url, token, kind: 'remote',
      ...(connectionId ? { connectionId } : {}),
    };
  } catch (error) {
    throw new PairingError(error.message);
  }
}

function parseJson(obj) {
  const legacyHost = obj.ip ?? obj.i ?? obj.host;
  const legacyPort = Number(obj.port ?? obj.p);
  const candidate = obj.url ?? obj.u ?? (legacyHost && legacyPort ? `ws://${legacyHost}:${legacyPort}` : '');
  const token = obj.token ?? obj.t;
  if (!candidate || !token) {
    throw new PairingError('Pairing JSON missing URL or token');
  }
  try {
    const url = normalizeEndpointUrl(candidate);
    const name = obj.name ?? obj.n ?? new URL(url).hostname;
    const connectionId = obj.connection_id ?? obj.c ?? '';
    return {
      name, url, token, kind: 'remote',
      ...(connectionId ? { connectionId: String(connectionId) } : {}),
    };
  } catch (error) {
    throw new PairingError(error.message);
  }
}
