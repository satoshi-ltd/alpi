import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockCall = vi.fn();
const AUTH_FAILED = -32099;
class RpcError extends Error {
  constructor(code) {
    super(`rpc:${code}`);
    this.code = code;
  }
}

vi.mock('./rpc', () => ({
  call: (...args) => mockCall(...args),
  AUTH_FAILED,
  RpcError,
}));

beforeEach(() => {
  mockCall.mockReset();
});

describe('probe', () => {
  it('returns an object with status + version + deviceName, never a bare string', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ version: '0.6.3', device_name: 'Macbook.Pro' });
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(typeof result).toBe('object');
    expect(result).toEqual({ status: 'online', version: '0.6.3', deviceName: 'Macbook.Pro' });
    expect(result === 'online').toBe(false);
  });

  it('reports deviceName=null when the daemon predates 0.6.3 (no device_name field)', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ version: '0.5.0' });
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'online', version: '0.5.0', deviceName: null });
  });

  it('treats blank/whitespace device_name as null so the pairing flow falls back to the URL name', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ version: '0.6.3', device_name: '   ' });
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'online', version: '0.6.3', deviceName: null });
  });

  it('marks offline when the summaries call rejects with a network error', async () => {
    const { probe } = await import('./probe');
    mockCall.mockRejectedValueOnce(new Error('ECONNREFUSED'));
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'offline', version: null, deviceName: null });
  });

  it('marks auth-failed when the token is rejected', async () => {
    const { probe } = await import('./probe');
    mockCall.mockRejectedValueOnce(new RpcError(AUTH_FAILED));
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'auth-failed', version: null, deviceName: null });
  });

  it('online stays online when host.version is missing (older daemons)', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new Error('unknown method'));
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'online', version: null, deviceName: null });
  });

  it('unknown status when no endpoint is passed', async () => {
    const { probe } = await import('./probe');
    const result = await probe(null);
    expect(result).toEqual({ status: 'unknown', version: null, deviceName: null });
    expect(mockCall).not.toHaveBeenCalled();
  });
});
