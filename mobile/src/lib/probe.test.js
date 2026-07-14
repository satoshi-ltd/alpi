import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockCall = vi.fn();
const AUTH_FAILED = -32099;
class RpcError extends Error {
  constructor(code, data = null) {
    super(`rpc:${code}`);
    this.code = code;
    this.data = data;
  }
}

vi.mock('./rpc', () => ({
  call: (...args) => mockCall(...args),
  AUTH_FAILED,
  RpcError,
}));
vi.mock('expo-constants', () => ({
  default: { expoConfig: { version: '0.2.15' } },
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
    expect(result).toEqual({ status: 'online', version: '0.6.6', updateAvailable: null, deviceName: 'Macbook.Pro', deviceId: 'mac-uuid', role: null, summaries: {} });
    expect(result === 'online').toBe(false);
    expect(mockCall).toHaveBeenNthCalledWith(
      3,
      expect.any(Object),
      'host.connections.register_device',
      expect.objectContaining({ client: 'mobile', app_version: '0.2.15' }),
      { timeoutMs: 2000 },
    );
  });

  it('treats blank/whitespace device_name + device_id as null so the pairing flow rejects on missing daemon identity', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ version: '0.6.6', device_name: '   ', device_id: '  ' });
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'online', version: '0.6.6', updateAvailable: null, deviceName: null, deviceId: null, role: null, summaries: {} });
  });

  it('marks offline when the summaries call rejects with a network error', async () => {
    const { probe } = await import('./probe');
    mockCall.mockRejectedValueOnce(new Error('ECONNREFUSED'));
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'offline', version: null, updateAvailable: null, deviceName: null, deviceId: null, role: null, summaries: null });
  });

  it('marks auth-failed when the token is rejected', async () => {
    const { probe } = await import('./probe');
    mockCall.mockRejectedValueOnce(new RpcError(AUTH_FAILED));
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'auth-failed', version: null, updateAvailable: null, deviceName: null, deviceId: null, role: null, summaries: null });
  });

  it('marks disabled when the host has paused the connection', async () => {
    const { probe } = await import('./probe');
    mockCall.mockRejectedValueOnce(new RpcError(AUTH_FAILED, { reason: 'connection-disabled' }));
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'disabled', version: null, updateAvailable: null, deviceName: null, deviceId: null, role: null, summaries: null });
  });

  it('online with null deviceId when host.version transiently fails — pairing layer surfaces the missing-identity error', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new Error('timeout'));
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result).toEqual({ status: 'online', version: null, updateAvailable: null, deviceName: null, deviceId: null, role: null, summaries: {} });
  });

  it('captures role from host.version response', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ version: '0.6.28', device_name: 'mbp', device_id: 'u', role: 'member' });
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result.role).toBe('member');
  });

  it('captures update_available from host.version response', async () => {
    const { probe } = await import('./probe');
    mockCall
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ version: '0.9.4', update_available: '0.9.5', device_name: 'mbp', device_id: 'u' });
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result.updateAvailable).toBe('0.9.5');
  });

  it('unknown status when no endpoint is passed', async () => {
    const { probe } = await import('./probe');
    const result = await probe(null);
    expect(result).toEqual({ status: 'unknown', version: null, updateAvailable: null, deviceName: null, deviceId: null, role: null, summaries: null });
    expect(mockCall).not.toHaveBeenCalled();
  });
});

describe('probe summaries payload (cache seed source)', () => {
  it('returns the summaries payload on success so the caller can seed the cache', async () => {
    const { probe } = await import('./probe');
    const payload = { profiles: [{ name: 'default' }] };
    mockCall
      .mockResolvedValueOnce(payload)
      .mockResolvedValueOnce({ version: '0.10.11', device_name: 'x', device_id: 'y' });
    const result = await probe({ ip: '100.64.0.1', port: 49200, token: 't' });
    expect(result.summaries).toBe(payload);
  });
});
