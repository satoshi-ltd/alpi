import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { reset, state } from './mocks/firstRun.js';

afterEach(cleanup);

const h = vi.hoisted(() => ({ params: {}, push: vi.fn(), replace: vi.fn(), call: vi.fn(), probe: vi.fn() }));

vi.mock('react-native', () => import('./mocks/firstRun.js'));
vi.mock('../src/theme/ThemeContext', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Button', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Fold', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Busy', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Icon', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/KeyboardPane', () => import('./mocks/firstRun.js'));
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }) }));
vi.mock('expo-camera', () => ({ CameraView: () => React.createElement('div', { 'data-camera': '1' }), useCameraPermissions: () => [{ granted: true }, vi.fn(), vi.fn()] }));
vi.mock('expo-clipboard', () => ({ getStringAsync: vi.fn(async () => '') }));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.7.0' } } }));
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, back: vi.fn(), replace: h.replace, canGoBack: () => true }),
  usePathname: () => '/pair',
  useLocalSearchParams: () => h.params,
}));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ addConnection: vi.fn() }) }));
vi.mock('../src/lib/rpc', async () => {
  const actual = await vi.importActual('../src/lib/rpc');
  return { ...actual, call: (...args) => h.call(...args) };
});
vi.mock('../src/lib/probe', () => ({ probe: (...args) => h.probe(...args) }));
vi.mock('../src/features/aln/notify', () => ({ getPermissionStatus: vi.fn(async () => 'undetermined'), requestPermission: vi.fn(async () => 'granted') }));
vi.mock('../src/lib/biometric', () => ({
  biometricCapabilities: vi.fn(async () => ({ hasHardware: false, enrolled: false, label: 'Biometric' })),
  getBiometricPref: vi.fn(async () => false),
  setBiometricPref: vi.fn(async () => {}),
  authenticate: vi.fn(async () => true),
}));

import Onboarding from '../app/onboarding.jsx';
import Pair from '../app/pair.jsx';
import PairSuccess from '../app/paired.jsx';

const style = (el) => JSON.parse(el.getAttribute('data-style') ?? '{}');
const stepState = (label) => screen.getByText(label).closest('[data-state]').getAttribute('data-state');
const primaries = () => [...document.querySelectorAll('button[data-variant="primary"]')];

const LINK = 'alpi://device?url=ws%3A%2F%2F100.1.2.3%3A49200&name=casa&pairing_token=abc';

beforeEach(() => {
  reset();
  h.params = {};
  h.push.mockReset();
  h.replace.mockReset();
  h.call.mockReset();
  h.probe.mockReset();
  h.call.mockImplementation(async (_endpoint, method) => (method === 'host.connections.exchange_pairing' ? { token: 'device-token' } : {}));
});

const pairWith = async (link) => {
  fireEvent.change(document.querySelector('[data-pair-input]'), { target: { value: link } });
  fireEvent.click(screen.getByText('Pair'));
};

describe('welcome', () => {
  it('opens the camera straight from Scan QR and says where a link comes from', () => {
    render(<Onboarding />);
    expect(screen.getByText('Where do I get a link?')).toBeTruthy();
    expect(screen.getByText('In the alpi desktop app')).toBeTruthy();
    expect(screen.getByText('Settings → Connections → New connection')).toBeTruthy();
    expect(screen.getByText('In a terminal on the host')).toBeTruthy();
    expect(screen.getByText('alpi setup → Connections → New connection')).toBeTruthy();
    fireEvent.click(screen.getByText('Scan QR'));
    expect(h.push).toHaveBeenCalledWith({ pathname: '/pair', params: { mode: 'scan' } });
    fireEvent.click(screen.getByText('Paste link'));
    expect(h.push).toHaveBeenLastCalledWith('/pair');
  });

  it('keeps every shipped string', () => {
    const { container } = render(<Onboarding />);
    expect(screen.getByText('Pair with your alpi')).toBeTruthy();
    expect(screen.getByText('alpi runs on a computer or a server. Pair this phone once and its profiles come with you.')).toBeTruthy();
    expect(container.textContent).not.toMatch(/Connect to your alpi|Scan QR code|Paste a link instead/);
  });

  it('has one primary, Scan QR at 56 pt, over the ghost Paste link at 48 pt, both full width', () => {
    render(<Onboarding />);
    expect(primaries().map((b) => b.textContent)).toEqual(['Scan QR']);
    const scan = screen.getByText('Scan QR');
    const paste = screen.getByText('Paste link');
    expect([scan.dataset.size, scan.dataset.height, scan.dataset.full]).toEqual(['hero', '56', 'true']);
    expect([paste.dataset.variant, paste.dataset.size, paste.dataset.height]).toEqual(['ghost', 'lg', '48']);
    expect(scan.compareDocumentPosition(paste) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('anchors the actions below the scrolling page, 16 pt above the safe area, on the 16 pt edge', () => {
    render(<Onboarding />);
    const scroll = document.querySelector('[data-scroll]');
    const actions = screen.getByText('Scan QR').parentElement;
    const bar = actions.parentElement;
    expect(scroll.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(style(bar)).toEqual({ paddingHorizontal: 16, paddingTop: 16, paddingBottom: 50 });
    expect(style(actions)).toMatchObject({ gap: 8, maxWidth: 480, alignSelf: 'flex-start' });
    expect(JSON.parse(scroll.getAttribute('data-content'))).toMatchObject({ paddingTop: 71, paddingHorizontal: 16 });
  });

  it('starts the mark ink, title, sentence and sources on one left edge with nothing centred', () => {
    const { container } = render(<Onboarding />);
    const column = screen.getByText('Pair with your alpi').parentElement;
    expect(style(column)).toMatchObject({ maxWidth: 480, alignSelf: 'flex-start' });
    const mark = container.querySelector('[data-fold]');
    expect(mark.dataset.size).toBe('72');
    expect(style(mark.parentElement).marginLeft).toBeCloseTo(-12.42, 2);
    for (const el of container.querySelectorAll('[data-style]')) {
      expect(style(el).textAlign, el.textContent).toBeUndefined();
    }
    expect(style(screen.getByText('Pair with your alpi'))).toMatchObject({ fontSize: 28, lineHeight: 36, marginTop: 24 });
  });

  it('moves the column to the 24 pt edge on a fold, still 480 wide at most', () => {
    state.width = 852;
    state.height = 884;
    render(<Onboarding />);
    const bar = screen.getByText('Scan QR').parentElement.parentElement;
    expect(style(bar).paddingHorizontal).toBe(24);
    expect(JSON.parse(document.querySelector('[data-scroll]').getAttribute('data-content')).paddingHorizontal).toBe(24);
    expect(style(screen.getByText('Pair with your alpi').parentElement).maxWidth).toBe(480);
  });

  it('wraps at the Largest text step without clipping: no line limits, the page scrolls', () => {
    state.scale = 1.3;
    const { container } = render(<Onboarding />);
    expect(document.querySelector('[data-scroll]')).toBeTruthy();
    expect(container.innerHTML).not.toMatch(/numberOfLines/);
    expect(style(screen.getByText('Pair with your alpi')).fontSize).toBeGreaterThan(28);
  });
});

describe('pairing', () => {
  it('lands on the camera when Scan QR opened the pairing screen', () => {
    h.params = { mode: 'scan' };
    const { container } = render(<Pair />);
    expect(container.querySelector('[data-camera]')).toBeTruthy();
  });

  it('names the host it cannot reach, keeps the link and offers to try again as the one primary', async () => {
    h.call.mockRejectedValue(Object.assign(new Error('connection failed to ws://100.1.2.3:49200'), { code: -32001, transport: true }));
    render(<Pair />);
    await pairWith(LINK);
    await waitFor(() => expect(screen.getByText("Can't reach casa")).toBeTruthy());
    expect(stepState('Reaching casa')).toBe('fail');
    expect(stepState('Link read')).toBe('done');
    expect(document.querySelector('[data-pair-input]').value).toBe(LINK);
    expect(primaries().map((b) => b.textContent)).toEqual(['Try again']);
    expect(screen.getByText('Scan QR').dataset.variant).toBe('ghost');
    expect(screen.getByText("Can't reach casa").parentElement.getAttribute('role')).toBe('alert');
    expect(style(screen.getByText("Can't reach casa")).color).toBe('#b73737');
  });

  it('asks for a new link when the host says this one was used, clears it, and pairs the next one pasted', async () => {
    h.call.mockRejectedValueOnce(Object.assign(new Error('pairing-used'), { code: -32011 }));
    h.probe.mockResolvedValue({ status: 'online', deviceId: 'd1', deviceName: 'casa', role: 'admin' });
    render(<Pair />);
    await pairWith(LINK);
    await waitFor(() => expect(screen.getByText('This link was already used or has expired')).toBeTruthy());
    expect(stepState('Signing in')).toBe('fail');
    expect(stepState('Reaching casa')).toBe('done');
    expect(document.querySelector('[data-pair-input]').value).toBe('');
    expect(primaries().map((b) => b.textContent)).toEqual(['Use a new link']);
    await pairWith(LINK);
    await waitFor(() => expect(h.replace).toHaveBeenCalledWith(expect.objectContaining({ pathname: '/paired' })));
    expect(h.call.mock.calls.filter(([, m]) => m === 'host.connections.exchange_pairing')).toHaveLength(2);
  });

  it('sends the phone to its inbox when the link was spent but the connection was kept', async () => {
    h.probe.mockResolvedValue({ status: 'offline' });
    render(<Pair />);
    await pairWith(LINK);
    await waitFor(() => expect(screen.getByText(/This phone kept the connection/)).toBeTruthy());
    expect(screen.queryByText('Scan QR')).toBeNull();
    fireEvent.click(screen.getByText('Open inbox'));
    expect(h.replace).toHaveBeenCalledWith('/');
    expect(h.call.mock.calls.filter(([, m]) => m === 'host.connections.exchange_pairing')).toHaveLength(1);
  });

  it('opens the paired screen with the host, the role and what is shared', async () => {
    h.probe.mockResolvedValue({ status: 'online', deviceId: 'd1', deviceName: 'casa', role: 'member', summaries: { profiles: [{ name: 'doc' }, { name: 'abby' }] } });
    render(<Pair />);
    await pairWith(LINK);
    await waitFor(() => expect(h.replace).toHaveBeenCalled());
    expect(h.replace).toHaveBeenCalledWith({ pathname: '/paired', params: { host: 'casa', role: 'member', shared: '2' } });
  });
});

describe('paired', () => {
  it('names the host and the role', () => {
    h.params = { host: 'casa', role: 'member', shared: '2' };
    render(<PairSuccess />);
    expect(screen.getByText('Paired with casa')).toBeTruthy();
    expect(screen.getByText('member · 2 profiles shared')).toBeTruthy();
  });

  it('tells an admin it sees every profile', () => {
    h.params = { host: 'casa', role: 'admin' };
    render(<PairSuccess />);
    expect(screen.getByText('admin · all profiles')).toBeTruthy();
  });
});
