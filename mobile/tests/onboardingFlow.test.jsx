import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ params: {}, push: vi.fn(), replace: vi.fn(), call: vi.fn(), probe: vi.fn() }));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityRole, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, hitSlop, style, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress }, children instanceof Function ? children({ pressed: false }) : children);
  return {
    View,
    Text,
    Pressable,
    Platform: { OS: 'ios', constants: { Model: 'iPhone' }, select: (sel) => sel?.ios ?? sel?.default },
    ScrollView: ({ children }) => React.createElement('div', {}, children),
    KeyboardAvoidingView: ({ children }) => React.createElement('div', {}, children),
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    TextInput: ({ value, onChangeText, style, ...p }) =>
      React.createElement('input', { 'data-pair-input': '1', value: value ?? '', onChange: (e) => onChangeText?.(e.target.value) }),
  };
});
vi.mock('expo-camera', () => ({ CameraView: () => React.createElement('div', { 'data-camera': '1' }), useCameraPermissions: () => [{ granted: true }, vi.fn()] }));
vi.mock('expo-clipboard', () => ({ getStringAsync: vi.fn(async () => '') }));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.7.0' } } }));
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, back: vi.fn(), replace: h.replace, canGoBack: () => true }),
  usePathname: () => '/pair',
  useLocalSearchParams: () => h.params,
}));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', danger: '#f00', dangerText: '#b00', line: '#ddd', bgInput: '#fafafa', hover: '#eee' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15, xl: 18, display: 28 },
    lineHeights: { normal: 1.5, relaxed: 1.6 },
    mobile: {},
  }),
}));
vi.mock('../src/components/Button', () => ({
  Button: ({ title, onPress, disabled }) => React.createElement('button', { type: 'button', onClick: onPress, disabled }, title),
}));
vi.mock('../src/components/Icon', () => ({ Icon: () => null }));
vi.mock('../src/components/Fold', () => ({ Fold: () => null }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ addConnection: vi.fn() }) }));
vi.mock('../src/lib/rpc', async () => {
  const actual = await vi.importActual('../src/lib/rpc');
  return { ...actual, call: (...args) => h.call(...args) };
});
vi.mock('../src/lib/probe', () => ({ probe: (...args) => h.probe(...args) }));

import Onboarding from '../app/onboarding.jsx';
import Pair from '../app/pair.jsx';
import PairSuccess from '../app/paired.jsx';

const stepState = (label) => screen.getByText(label).closest('[data-state]').getAttribute('data-state');

const LINK = 'alpi://device?url=ws%3A%2F%2F100.1.2.3%3A49200&name=casa&pairing_token=abc';

beforeEach(() => {
  h.params = {};
  h.push.mockReset();
  h.replace.mockReset();
  h.call.mockReset();
  h.probe.mockReset();
  h.call.mockImplementation(async (_endpoint, method) => (method === 'host.connections.exchange_pairing' ? { token: 'device-token' } : {}));
});

const pairWith = async (link) => {
  fireEvent.change(document.querySelector('[data-pair-input]'), { target: { value: link } });
  fireEvent.click(screen.getAllByRole('button').find((b) => /^pair$/i.test(b.textContent.trim())));
};

describe('welcome', () => {
  it('opens the camera straight from Scan QR and says where a link comes from', () => {
    render(<Onboarding />);
    expect(screen.getByText('Where do I get a link?')).toBeTruthy();
    expect(screen.getByText(/Settings → Connections → New connection/)).toBeTruthy();
    fireEvent.click(screen.getByText('Scan QR'));
    expect(h.push).toHaveBeenCalledWith({ pathname: '/pair', params: { mode: 'scan' } });
    fireEvent.click(screen.getByText('Paste link'));
    expect(h.push).toHaveBeenLastCalledWith('/pair');
  });

  it('lands on the camera when Scan QR opened the pairing screen', () => {
    h.params = { mode: 'scan' };
    const { container } = render(<Pair />);
    expect(container.querySelector('[data-camera]')).toBeTruthy();
  });
});

describe('pairing', () => {
  it('names the host it cannot reach, keeps the link and offers to try again', async () => {
    h.call.mockRejectedValue(Object.assign(new Error('connection failed to ws://100.1.2.3:49200'), { code: -32001, transport: true }));
    render(<Pair />);
    await pairWith(LINK);
    await waitFor(() => expect(screen.getByText("Can't reach casa")).toBeTruthy());
    expect(stepState('Reaching casa')).toBe('fail');
    expect(stepState('Link read')).toBe('done');
    expect(document.querySelector('[data-pair-input]').value).toBe(LINK);
    expect(screen.getByText('Try again')).toBeTruthy();
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
    await pairWith(LINK);
    await waitFor(() => expect(h.replace).toHaveBeenCalledWith(expect.objectContaining({ pathname: '/paired' })));
    expect(h.call.mock.calls.filter(([, m]) => m === 'host.connections.exchange_pairing')).toHaveLength(2);
  });

  it('sends the phone to its inbox when the link was spent but the connection was kept', async () => {
    h.probe.mockResolvedValue({ status: 'offline' });
    render(<Pair />);
    await pairWith(LINK);
    await waitFor(() => expect(screen.getByText(/This phone kept the connection/)).toBeTruthy());
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
