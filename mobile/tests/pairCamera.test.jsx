import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { act } from 'react';

import { Linking, flip, reset, state } from './mocks/firstRun.js';

afterEach(cleanup);

const h = vi.hoisted(() => ({ cam: null, call: vi.fn(), permission: { granted: true }, request: vi.fn(), refresh: vi.fn() }));

vi.mock('react-native', () => import('./mocks/firstRun.js'));
vi.mock('../src/theme/ThemeContext', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Button', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Fold', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Busy', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Icon', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/KeyboardPane', () => import('./mocks/firstRun.js'));
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }) }));
vi.mock('expo-camera', () => ({
  CameraView: (props) => {
    h.cam = props;
    return React.createElement('div', { 'data-camera': '1' });
  },
  useCameraPermissions: () => [h.permission, h.request, h.refresh],
}));
vi.mock('expo-clipboard', () => ({ getStringAsync: vi.fn(async () => '') }));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.3.1' } } }));
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn(), canGoBack: () => true }),
  usePathname: () => '/pair',
  useLocalSearchParams: () => ({ mode: 'scan' }),
}));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ addConnection: vi.fn() }) }));
vi.mock('../src/lib/rpc', async () => ({ ...(await vi.importActual('../src/lib/rpc')), call: (...args) => h.call(...args) }));
vi.mock('../src/lib/probe', () => ({ probe: vi.fn(async () => ({ status: 'offline' })) }));

import Pair from '../app/pair.jsx';

const style = (el) => JSON.parse(el.getAttribute('data-style') ?? '{}');
const primaries = () => [...document.querySelectorAll('button[data-variant="primary"]')];

beforeEach(() => {
  reset();
  h.permission = { granted: true };
  h.request.mockReset();
  h.refresh.mockReset();
});

describe('scan', () => {
  it('is the camera, a header on the 16 pt edge and one bottom secondary lg, no arrow and no primary', () => {
    const { container } = render(<Pair />);
    expect(container.querySelector('[data-camera]')).toBeTruthy();
    expect(screen.getByText('Pair this phone')).toBeTruthy();
    expect(screen.getByText('Scan the QR shown on your daemon')).toBeTruthy();
    const paste = screen.getByText('Paste link');
    expect([paste.dataset.variant, paste.dataset.size, paste.dataset.height, paste.dataset.full]).toEqual(['secondary', 'lg', '48', 'true']);
    expect(document.querySelectorAll('button')).toHaveLength(1);
    expect(primaries()).toHaveLength(0);
    expect(container.querySelector('[data-icon], [aria-label="Back to the pairing link"]')).toBeNull();
    expect(screen.queryByText('Paste alpi:// link instead')).toBeNull();
    expect(style(paste.parentElement.parentElement)).toMatchObject({ paddingHorizontal: 16, paddingBottom: 50 });
  });

  it('draws the bottom button with the dark palette so it shows on the black camera in light mode', () => {
    state.mode = 'light';
    render(<Pair />);
    expect(screen.getByText('Paste link').dataset.dark).toBe('true');
  });

  it('leaves the camera for the paste page through the one bottom button', () => {
    const { container } = render(<Pair />);
    fireEvent.click(screen.getByText('Paste link'));
    expect(container.querySelector('[data-camera]')).toBeNull();
    expect(screen.getByText('Pair')).toBeTruthy();
  });
});

describe('scan guards', () => {
  it('pairs once when the camera delivers two codes in the same tick', async () => {
    h.call.mockReset();
    h.call.mockReturnValue(new Promise(() => {}));
    render(<Pair />);
    const data = 'alpi://device?url=ws%3A%2F%2F100.1.2.3%3A49200&name=casa&pairing_token=abc';
    await act(async () => {
      h.cam.onBarcodeScanned({ data });
      h.cam.onBarcodeScanned({ data });
    });
    expect(h.call.mock.calls.filter(([, m]) => m === 'host.connections.exchange_pairing')).toHaveLength(1);
  });
});

describe('camera not allowed', () => {
  beforeEach(() => {
    h.permission = { granted: false, canAskAgain: true, status: 'undetermined' };
  });

  it('is a page on the theme ground with Grant access as the one primary over Paste link', () => {
    const { container } = render(<Pair />);
    expect(container.querySelector('[data-camera]')).toBeNull();
    expect(screen.getByText('camera · not allowed')).toBeTruthy();
    expect(screen.getByText('Camera permission needed to scan the pairing QR.')).toBeTruthy();
    expect(primaries().map((b) => b.textContent)).toEqual(['Grant access']);
    expect(screen.getByText('Grant access').dataset.size).toBe('hero');
    expect(screen.getByText('Paste link').dataset.variant).toBe('ghost');
    expect(container.innerHTML).not.toContain('"backgroundColor":"#000"');
    fireEvent.click(screen.getByText('Grant access'));
    expect(h.request).toHaveBeenCalledTimes(1);
  });

  it('offers Open settings when the system will not ask again, and opens the app settings', () => {
    h.permission = { granted: false, canAskAgain: false, status: 'denied' };
    render(<Pair />);
    expect(screen.queryByText('Grant access')).toBeNull();
    expect(primaries().map((b) => b.textContent)).toEqual(['Open settings']);
    fireEvent.click(screen.getByText('Open settings'));
    expect(Linking.openSettings).toHaveBeenCalledTimes(1);
    expect(h.request).not.toHaveBeenCalled();
  });

  it('checks the permission again when the app comes back from the system settings', () => {
    h.permission = { granted: false, canAskAgain: false, status: 'denied' };
    render(<Pair />);
    act(() => flip('background'));
    expect(h.refresh).not.toHaveBeenCalled();
    act(() => flip('active'));
    expect(h.refresh).toHaveBeenCalledTimes(1);
  });

  it('leaves for the paste page with the ghost', () => {
    render(<Pair />);
    fireEvent.click(screen.getByText('Paste link'));
    expect(screen.getByText('Pair')).toBeTruthy();
  });

  it('puts the mark on the edge and anchors the actions 16 pt above the safe area', () => {
    const { container } = render(<Pair />);
    expect(container.querySelector('[data-fold]').dataset.size).toBe('72');
    const bar = screen.getByText('Grant access').parentElement.parentElement;
    expect(style(bar)).toEqual({ paddingHorizontal: 16, paddingTop: 16, paddingBottom: 50 });
  });
});
