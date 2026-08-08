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

export async function exchangePairing(endpoint, metadata, rpc, onExchanged) {
  if (!endpoint?.pairingToken) return endpoint;
  const result = await rpc(
    { name: endpoint.name, url: endpoint.url, kind: 'remote' },
    'host.connections.exchange_pairing',
    {
      pairing_token: endpoint.pairingToken,
      client: 'mobile',
      name: metadata.name,
      app_version: metadata.appVersion,
    },
  );
  if (!result?.token) throw new PairingError('Pairing exchange returned no device token');
  const { pairingToken: _used, ...base } = endpoint;
  const exchanged = {
    ...base,
    token: result.token,
    connectionId: result.connection_id || endpoint.connectionId,
    deviceId: result.device_id,
    role: result.role || null,
    name: result.label || endpoint.name,
  };
  if (onExchanged) await onExchanged(exchanged);
  return exchanged;
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
  const pairingToken = params.get('pairing_token');
  const candidate = params.get('url') || (legacyHost && legacyPort ? `ws://${legacyHost}:${legacyPort}` : '');
  if (!candidate || (!token && !pairingToken)) {
    throw new PairingError('alpi:// link missing URL or pairing credential');
  }
  try {
    const url = normalizeEndpointUrl(candidate);
    const name = params.get('name') ?? new URL(url).hostname;
    const connectionId = params.get('connection_id') || params.get('c') || '';
    return {
      name, url, kind: 'remote',
      ...(token ? { token } : {}),
      ...(pairingToken ? { pairingToken } : {}),
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
  const pairingToken = obj.pairing_token ?? obj.g;
  if (!candidate || (!token && !pairingToken)) {
    throw new PairingError('Pairing JSON missing URL or pairing credential');
  }
  try {
    const url = normalizeEndpointUrl(candidate);
    const name = obj.name ?? obj.n ?? new URL(url).hostname;
    const connectionId = obj.connection_id ?? obj.c ?? '';
    return {
      name, url, kind: 'remote',
      ...(token ? { token } : {}),
      ...(pairingToken ? { pairingToken } : {}),
      ...(connectionId ? { connectionId: String(connectionId) } : {}),
    };
  } catch (error) {
    throw new PairingError(error.message);
  }
}
