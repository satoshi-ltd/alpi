import { describe, expect, it } from 'vitest';

import { PairingError, parsePairing } from './pairing.js';

describe('parsePairing', () => {
  it('accepts the URL payload without a version marker', () => {
    expect(parsePairing(JSON.stringify({
      u: 'wss://client.example.com', n: 'Client', t: 'secret',
    }))).toEqual({
      name: 'Client', url: 'wss://client.example.com', token: 'secret', kind: 'remote',
    });
  });

  it('keeps legacy host and port pairing links compatible', () => {
    expect(parsePairing('alpi://device?host=100.64.0.1&port=49200&name=Old&token=secret'))
      .toEqual({
        name: 'Old', url: 'ws://100.64.0.1:49200', token: 'secret', kind: 'remote',
      });
  });

  it('preserves the stable server connection id from links and QR payloads', () => {
    expect(parsePairing(
      'alpi://device?url=wss%3A%2F%2Fclient.example.com&name=Client&token=secret&connection_id=conn-1',
    )).toMatchObject({ connectionId: 'conn-1' });
    expect(parsePairing(JSON.stringify({
      u: 'wss://client.example.com', n: 'Client', t: 'secret', c: 'conn-1',
    }))).toMatchObject({ connectionId: 'conn-1' });
  });

  it('rejects non-WebSocket and credential-bearing URLs', () => {
    expect(() => parsePairing('{"u":"https://client.example.com","t":"secret"}'))
      .toThrow(PairingError);
    expect(() => parsePairing('{"u":"wss://user:pass@client.example.com","t":"secret"}'))
      .toThrow(PairingError);
  });
});
