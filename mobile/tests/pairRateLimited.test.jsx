import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => import('./mocks/firstRun.js'));
vi.mock('../src/theme/ThemeContext', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Button', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Fold', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Busy', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Icon', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/KeyboardPane', () => import('./mocks/firstRun.js'));
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }) }));
vi.mock('expo-camera', () => ({ CameraView: () => null, useCameraPermissions: () => [{ granted: false }, vi.fn()] }));
vi.mock('expo-clipboard', () => ({ getStringAsync: vi.fn(async () => '') }));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.4.9' } } }));
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn(), canGoBack: () => true }),
  usePathname: () => '/pair',
  useLocalSearchParams: () => ({}),
}));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ addConnection: vi.fn() }) }));

const callMock = vi.fn();
vi.mock('../src/lib/rpc', async () => {
  const actual = await vi.importActual('../src/lib/rpc');
  return { ...actual, call: (...args) => callMock(...args) };
});
vi.mock('../src/lib/probe', () => ({ probe: vi.fn() }));

import Pair from '../app/pair.jsx';
import { RATE_LIMITED, RATE_LIMITED_MESSAGE, RpcError } from '../src/lib/rpc';

const LINK = 'alpi://device?url=ws%3A%2F%2Fcasa%3A49200&name=casa&pairing_token=grant-123';

describe('Pair screen under a throttled daemon', () => {
  it('shows the rate-limit notice, keeps the link and does not resend the exchange', async () => {
    callMock.mockRejectedValue(new RpcError(RATE_LIMITED, RATE_LIMITED_MESSAGE, { close_code: 1013, reason: 'auth-rate-limited' }));
    render(React.createElement(Pair));
    const input = document.querySelector('[data-pair-input]');
    fireEvent.change(input, { target: { value: LINK } });
    fireEvent.click(screen.getByText('Pair'));

    await waitFor(() => expect(screen.getByText('Too many attempts')).toBeTruthy());
    expect(callMock).toHaveBeenCalledTimes(1);
    expect(callMock.mock.calls[0][1]).toBe('host.connections.exchange_pairing');
    expect(document.querySelector('[data-pair-input]').value).toBe(LINK);
    expect(screen.queryByText(/re-pair|Token rejected/i)).toBeNull();
  });
});
