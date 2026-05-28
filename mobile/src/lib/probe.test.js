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
  it('returns {status, version, deviceName, deviceId} — never a bare string', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ version: '0.6.6', device_name: 'Macbook.Pro', device_id: 'mac-uuid' });
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'online', version: '0.6.6', deviceName: 'Macbook.Pro', deviceId: 'mac-uuid', role: null });
    expect(result === 'online').toBe(false);
  });

  it('treats blank/whitespace device_name + device_id as null so the pairing flow rejects on missing daemon identity', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ version: '0.6.6', device_name: '   ', device_id: '  ' });
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'online', version: '0.6.6', deviceName: null, deviceId: null, role: null });
  });

  it('marks offline when the summaries call rejects with a network error', async () => {
    const { probe } = await import('./probe');
    mockCall.mockRejectedValueOnce(new Error('ECONNREFUSED'));
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'offline', version: null, deviceName: null, deviceId: null, role: null });
  });

  it('marks auth-failed when the token is rejected', async () => {
    const { probe } = await import('./probe');
    mockCall.mockRejectedValueOnce(new RpcError(AUTH_FAILED));
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'auth-failed', version: null, deviceName: null, deviceId: null, role: null });
  });

  it('online with null deviceId when host.version transiently fails — pairing layer surfaces the missing-identity error', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new Error('timeout'));
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'online', version: null, deviceName: null, deviceId: null, role: null });
  });

  it('captures role from host.version response', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ version: '0.6.28', device_name: 'mbp', device_id: 'u', role: 'member' });
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result.role).toBe('member');
  });

  it('unknown status when no endpoint is passed', async () => {
    const { probe } = await import('./probe');
    const result = await probe(null);
    expect(result).toEqual({ status: 'unknown', version: null, deviceName: null, deviceId: null, role: null });
    expect(mockCall).not.toHaveBeenCalled();
  });
});
