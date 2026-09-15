import { describe, expect, it, vi } from 'vitest';

const callMock = vi.fn();
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.4.9' } } }));
vi.mock('react-native', () => ({ Platform: { OS: 'ios', constants: { Model: 'iPhone' } } }));
vi.mock('../src/lib/rpc', async () => {
  const actual = await vi.importActual('../src/lib/rpc');
  return { ...actual, call: (...args) => callMock(...args) };
});

import { probe } from '../src/lib/probe';
import { RATE_LIMITED, RATE_LIMITED_MESSAGE, RpcError, AUTH_FAILED } from '../src/lib/rpc';

const endpoint = { id: 'ep-1', url: 'ws://casa:49200', token: 't' };

describe('probe rate-limited mapping', () => {
  it('reports rate-limited for the daemon throttle close and keeps auth-failed separate', async () => {
    callMock.mockRejectedValueOnce(new RpcError(RATE_LIMITED, RATE_LIMITED_MESSAGE, { close_code: 1013, reason: 'auth-rate-limited' }));
    expect((await probe(endpoint)).status).toBe('rate-limited');

    callMock.mockRejectedValueOnce(new RpcError(AUTH_FAILED, 'auth-failed'));
    expect((await probe(endpoint)).status).toBe('auth-failed');

    callMock.mockRejectedValueOnce(new RpcError(-32002, 'connection closed before response'));
    expect((await probe(endpoint)).status).toBe('offline');
  });
});
