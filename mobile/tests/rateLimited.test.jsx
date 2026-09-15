import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('../src/components/Banner', () => ({
  Banner: ({ kind, children, action }) =>
    React.createElement('div', { 'data-banner': kind, 'data-action': action ?? '' }, children),
}));

const probeMock = vi.fn();
vi.mock('../src/lib/probe', () => ({
  probe: (...args) => probeMock(...args),
  probeAll: vi.fn(async () => ({ status: new Map(), versions: new Map(), updates: new Map(), deviceIds: new Map(), roles: new Map() })),
}));
vi.mock('../src/lib/rpc', () => ({
  call: vi.fn(),
  callStream: vi.fn(),
  dropEndpointPool: vi.fn(),
}));
vi.mock('../src/lib/store', () => ({
  clearAll: vi.fn(),
  loadConnections: vi.fn(async () => ({ active_id: 'ep-1', connections: [{ id: 'ep-1', name: 'casa', url: 'ws://casa:49200', token: 't' }] })),
  removeConnection: vi.fn(),
  rolesFromConnections: () => new Map(),
  saveConnection: vi.fn(),
  setActiveConnection: vi.fn(),
  setDeviceIds: vi.fn(async () => ({ connections: [] })),
  setRoles: vi.fn(),
}));
vi.mock('../src/hooks/useCachedImage', () => ({ clearImageCache: vi.fn() }));
vi.mock('../src/hooks/useDaemonData', () => ({ seedCache: vi.fn() }));

import { DAEMON_STATUS_BANNERS, DaemonBanner, isDaemonDown } from '../src/components/DaemonBanner';
import { RATE_LIMITED_MESSAGE, RATE_LIMITED_STATUS } from '../src/lib/rateLimit';
import { EndpointProvider } from '../src/lib/EndpointProvider';
import { useEndpoint } from '../src/lib/EndpointContext';

const probeResult = (status) => ({ status, version: null, updateAvailable: null, deviceName: null, deviceId: null, role: null, summaries: null });

describe('rate-limited banner', () => {
  it('names the temporary throttle as a warning without a retry action or re-pair advice', () => {
    expect(isDaemonDown(RATE_LIMITED_STATUS)).toBe(true);
    expect(DAEMON_STATUS_BANNERS[RATE_LIMITED_STATUS].message).toBe(RATE_LIMITED_MESSAGE);
    render(React.createElement(DaemonBanner, { status: RATE_LIMITED_STATUS, paired: true, onRetry: vi.fn() }));
    const banner = document.querySelector('[data-banner]');
    expect(banner.getAttribute('data-banner')).toBe('warning');
    expect(banner.getAttribute('data-action')).toBe('');
    expect(screen.getByText(RATE_LIMITED_MESSAGE)).toBeTruthy();
    expect(RATE_LIMITED_MESSAGE).not.toMatch(/re-pair|token/i);
  });
});

function StatusProbe() {
  const { probeState, activeId } = useEndpoint();
  return React.createElement('span', { 'data-status': probeState.get(activeId) ?? 'unknown' });
}

const statusNow = () => document.querySelector('[data-status]')?.getAttribute('data-status');

describe('rate-limited reprobe', () => {
  beforeEach(() => {
    probeMock.mockReset();
  });

  it('waits a full minute between probes, recovers to online and stops on unmount', async () => {
    vi.useFakeTimers();
    let status = RATE_LIMITED_STATUS;
    probeMock.mockImplementation(async () => probeResult(status));
    try {
      const view = render(React.createElement(EndpointProvider, null, React.createElement(StatusProbe)));
      await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
      expect(statusNow()).toBe(RATE_LIMITED_STATUS);
      expect(probeMock).toHaveBeenCalledTimes(1);

      await act(async () => { await vi.advanceTimersByTimeAsync(59000); });
      expect(probeMock).toHaveBeenCalledTimes(1);

      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(probeMock).toHaveBeenCalledTimes(2);
      expect(statusNow()).toBe(RATE_LIMITED_STATUS);

      status = 'online';
      await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
      expect(probeMock).toHaveBeenCalledTimes(3);
      expect(statusNow()).toBe('online');

      await act(async () => { await vi.advanceTimersByTimeAsync(180000); });
      expect(probeMock).toHaveBeenCalledTimes(3);

      status = RATE_LIMITED_STATUS;
      view.unmount();
      await act(async () => { await vi.advanceTimersByTimeAsync(180000); });
      expect(probeMock).toHaveBeenCalledTimes(3);
    } finally {
      vi.useRealTimers();
    }
  });
});
