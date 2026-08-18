import { describe, expect, it } from 'vitest';

import { redirectSystemPath } from '../app/+native-intent';
import { pairingLinkFromParams } from '../src/lib/pairing';

const QUERY = 'url=ws%3A%2F%2Flocalhost%3A49200&name=pixel-9a&pairing_token=abc-123&connection_id=conn_1';

describe('redirectSystemPath', () => {
  it('sends a pairing link to the pair screen instead of a missing /device route', () => {
    expect(redirectSystemPath({ path: `alpi://device?${QUERY}` })).toBe(`/pair?${QUERY}`);
  });

  it('accepts the scheme-stripped forms the router may hand over', () => {
    for (const raw of [`/device?${QUERY}`, `device?${QUERY}`]) {
      expect(redirectSystemPath({ path: raw })).toBe(`/pair?${QUERY}`);
    }
  });

  it('forwards the query flat so no nested encoding can truncate the token', () => {
    const redirected = redirectSystemPath({ path: `alpi://device?${QUERY}` });
    const params = new URLSearchParams(redirected.slice(redirected.indexOf('?') + 1));
    expect(params.get('pairing_token')).toBe('abc-123');
    expect(params.get('url')).toBe('ws://localhost:49200');
    expect(params.get('connection_id')).toBe('conn_1');
  });

  it('leaves every other route untouched', () => {
    for (const raw of ['/', '/pair', '/chat/alpi', '/wg/site-a', '/outputs', 'alpi://chat/alpi', '/devices']) {
      expect(redirectSystemPath({ path: raw })).toBe(raw);
    }
  });

  it('passes a non-string path straight through', () => {
    expect(redirectSystemPath({ path: null })).toBe(null);
    expect(redirectSystemPath({ path: undefined })).toBe(undefined);
  });
});

describe('pairingLinkFromParams', () => {
  it('rebuilds a link the pairing parser accepts', () => {
    const link = pairingLinkFromParams({
      url: 'ws://localhost:49200',
      pairing_token: 'abc-123',
      name: 'pixel-9a',
      connection_id: 'conn_1',
    });
    const params = new URL(link).searchParams;
    expect(link.startsWith('alpi://device?')).toBe(true);
    expect(params.get('url')).toBe('ws://localhost:49200');
    expect(params.get('pairing_token')).toBe('abc-123');
  });

  it('survives the redirect round trip end to end', () => {
    const redirected = redirectSystemPath({ path: `alpi://device?${QUERY}` });
    const routed = Object.fromEntries(new URLSearchParams(redirected.slice(redirected.indexOf('?') + 1)));
    const params = new URL(pairingLinkFromParams(routed)).searchParams;
    expect(params.get('url')).toBe('ws://localhost:49200');
    expect(params.get('pairing_token')).toBe('abc-123');
  });

  it('accepts the legacy host/port form', () => {
    const link = pairingLinkFromParams({ host: '10.0.0.4', port: '49200', token: 'tok' });
    expect(new URL(link).searchParams.get('host')).toBe('10.0.0.4');
  });

  it('returns nothing when the params are not a pairing link', () => {
    expect(pairingLinkFromParams({})).toBe('');
    expect(pairingLinkFromParams(undefined)).toBe('');
    expect(pairingLinkFromParams({ url: 'ws://localhost:49200' })).toBe('');
    expect(pairingLinkFromParams({ pairing_token: 'abc' })).toBe('');
  });
});
