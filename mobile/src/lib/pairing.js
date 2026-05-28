// alpi://device?host=…&port=…&name=…&token=…  →  endpoint shape used by lib/store.

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
  const host = params.get('host');
  const port = Number(params.get('port'));
  const token = params.get('token');
  const name = params.get('name') ?? host;
  if (!host || !port || !token) {
    throw new PairingError('alpi:// link missing host, port, or token');
  }
  return { name, ip: host, port, token, kind: 'remote' };
}

function parseJson(obj) {
  const ip = obj.ip ?? obj.i ?? obj.host;
  const port = Number(obj.port ?? obj.p);
  const token = obj.token ?? obj.t;
  const name = obj.name ?? obj.n ?? ip;
  if (!ip || !port || !token) {
    throw new PairingError('Pairing JSON missing host, port, or token');
  }
  return { name, ip, port, token, kind: 'remote' };
}
