import { describe, expect, it } from 'vitest';

import { PairingError, exchangePairing, parsePairing } from './pairing.js';

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

  it('parses and exchanges one-time credentials without persisting them', async () => {
    const endpoint = parsePairing(JSON.stringify({
      u: 'wss://client.example.com', n: 'Client', g: 'one-time', c: 'conn-1',
    }));
    expect(endpoint).toMatchObject({ pairingToken: 'one-time', connectionId: 'conn-1' });
    const rpc = async (_target, method, params) => {
      expect(method).toBe('host.connections.exchange_pairing');
      expect(params).toEqual({
        pairing_token: 'one-time', client: 'mobile', name: 'iPhone', app_version: '0.3.1',
      });
      return {
        token: 'permanent', connection_id: 'conn-1', device_id: 'device-1',
        role: 'member', label: 'Home Alpi',
      };
    };

    const events = [];
    const exchanged = await exchangePairing(
      endpoint,
      { name: 'iPhone', appVersion: '0.3.1' },
      async (...args) => {
        events.push('exchange');
        return rpc(...args);
      },
      async (credential) => {
        events.push('persist');
        expect(credential).toMatchObject({ token: 'permanent', deviceId: 'device-1' });
      },
    );

    expect(events).toEqual(['exchange', 'persist']);
    expect(exchanged).toMatchObject({
      token: 'permanent', connectionId: 'conn-1', deviceId: 'device-1',
      role: 'member', name: 'Home Alpi',
    });
    expect(exchanged).not.toHaveProperty('pairingToken');
  });

  it('rejects an incomplete exchange response', async () => {
    await expect(exchangePairing(
      { name: 'Client', url: 'wss://client.example.com', pairingToken: 'grant' },
      { name: 'iPhone', appVersion: '0.3.1' },
      async () => ({}),
    )).rejects.toThrow(PairingError);
  });

  it('rejects non-WebSocket and credential-bearing URLs', () => {
    expect(() => parsePairing('{"u":"https://client.example.com","t":"secret"}'))
      .toThrow(PairingError);
    expect(() => parsePairing('{"u":"wss://user:pass@client.example.com","t":"secret"}'))
      .toThrow(PairingError);
  });
});
