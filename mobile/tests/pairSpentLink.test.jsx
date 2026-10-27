import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const { h } = vi.hoisted(() => ({
  h: { params: {}, replace: vi.fn(), spent: false, remember: vi.fn(), probe: { status: 'online', deviceId: 'd1', deviceName: 'Mac', role: 'admin', summaries: [] } },
}));

vi.mock('react-native', () => import('./mocks/firstRun.js'));
vi.mock('../src/theme/ThemeContext', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Button', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Fold', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Busy', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Icon', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/KeyboardPane', () => import('./mocks/firstRun.js'));
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }) }));
vi.mock('expo-camera', () => ({ CameraView: () => null, useCameraPermissions: () => [{ granted: false }, vi.fn(), vi.fn()] }));
vi.mock('expo-clipboard', () => ({ getStringAsync: vi.fn(async () => '') }));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.3.1' } } }));
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: h.replace, canGoBack: () => true }),
  usePathname: () => '/pair',
  useLocalSearchParams: () => h.params,
}));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ addConnection: vi.fn() }) }));

vi.mock('../src/lib/spentPairings', () => ({ isSpentPairing: async () => h.spent, rememberSpentPairing: h.remember }));
vi.mock('../src/lib/pairing', async (importOriginal) => ({ ...(await importOriginal()), exchangePairing: async (endpoint) => { const { pairingToken: _used, ...rest } = endpoint; return rest; } }));
vi.mock('../src/lib/probe', () => ({ probe: async () => h.probe }));
vi.mock('../src/lib/rpc', () => ({ call: async () => ({}) }));

import Pair from '../app/pair.jsx';
import { reset } from './mocks/firstRun.js';

beforeEach(reset);

const LINK = { url: 'ws://10.0.0.2:49200', pairing_token: 'tok-1', name: 'Mac', connection_id: 'conn_1' };

describe('Pair screen with a link handed over by the system', () => {
  it('prefills a fresh link', async () => {
    h.params = LINK;
    h.spent = false;
    h.replace.mockClear();
    render(<Pair />);
    await waitFor(() => expect(document.querySelector('input').value).toMatch(/^alpi:\/\/device\?url=/));
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('opens the link-used state, not the inbox, when the system hands the same link over again after it was used', async () => {
    h.params = LINK;
    h.spent = true;
    h.replace.mockClear();
    render(<Pair />);
    await waitFor(() => expect(screen.getByText('This link was already used or has expired')).toBeTruthy());
    expect(h.replace).not.toHaveBeenCalled();
    expect(document.querySelector('input').value).toBe('');
    expect(screen.getByText('Make a new one on the host and paste it here.')).toBeTruthy();
    expect(screen.getByText('Reaching Mac').closest('[data-state]').dataset.state).toBe('done');
    expect(screen.getByText('Signing in').closest('[data-state]').dataset.state).toBe('fail');
    expect([...document.querySelectorAll('button[data-variant="primary"]')].map((b) => b.textContent)).toEqual(['Use a new link']);
    expect(screen.getByText('Scan QR').dataset.variant).toBe('ghost');
  });

  it('empties and takes focus on the field when the user picks Use a new link', async () => {
    h.params = LINK;
    h.spent = true;
    render(<Pair />);
    await waitFor(() => expect(screen.getByText('Use a new link')).toBeTruthy());
    const field = document.querySelector('input');
    const focus = vi.spyOn(field, 'focus');
    fireEvent.click(screen.getByText('Use a new link'));
    expect(focus).toHaveBeenCalled();
    expect(screen.queryByText('This link was already used or has expired')).toBeNull();
    expect(screen.getByText('Pair').disabled).toBe(true);
  });
});

describe('Pair screen marks a used link as spent', () => {
  it('remembers the one-time token once the daemon has accepted it', async () => {
    h.params = LINK;
    h.spent = false;
    h.remember.mockClear();
    h.probe = { status: 'online', deviceId: 'd1', deviceName: 'Mac', role: 'admin', summaries: [] };
    render(<Pair />);
    await waitFor(() => expect(document.querySelector('input').value).toMatch(/^alpi:\/\/device/));
    fireEvent.click(screen.getByText('Pair'));
    await waitFor(() => expect(h.remember).toHaveBeenCalledWith('tok-1'));
  });

  it('does not remember a link whose exchange never happened', async () => {
    h.params = { ...LINK, url: 'not a url' };
    h.spent = false;
    h.remember.mockClear();
    render(<Pair />);
    await waitFor(() => expect(document.querySelector('input').value).not.toBe(''));
    fireEvent.click(screen.getByText('Pair'));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(h.remember).not.toHaveBeenCalled();
  });
});
