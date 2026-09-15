import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, hitSlop, style, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...p },
      children instanceof Function ? children({ pressed: false }) : children);
  return {
    View,
    Text,
    Pressable,
    Platform: { OS: 'ios', constants: { Model: 'iPhone' }, select: (sel) => sel?.ios ?? sel?.default },
    ScrollView: ({ children }) => React.createElement('div', {}, children),
    KeyboardAvoidingView: ({ children }) => React.createElement('div', {}, children),
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    TextInput: ({ value, onChangeText, style, ...p }) =>
      React.createElement('input', { ...p, 'data-pair-input': '1', value: value ?? '', onChange: (e) => onChangeText?.(e.target.value) }),
  };
});
vi.mock('expo-camera', () => ({ CameraView: () => null, useCameraPermissions: () => [{ granted: false }, vi.fn()] }));
vi.mock('expo-clipboard', () => ({ getStringAsync: vi.fn(async () => '') }));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.4.9' } } }));
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn(), canGoBack: () => true }),
  usePathname: () => '/pair',
  useLocalSearchParams: () => ({}),
}));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', danger: '#f00', line: '#ddd', bgInput: '#fafafa' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
    fontSizes: { xs: 11, md: 14, lg: 15, xl: 18, display: 28 },
    lineHeights: { normal: 1.5 },
    mobile: {},
  }),
}));
vi.mock('../src/components/Button', () => ({
  Button: ({ title, onPress, disabled }) => React.createElement('button', { type: 'button', onClick: onPress, disabled }, title),
}));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
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
    const pairButton = screen.getAllByRole('button').find((b) => /^pair$/i.test(b.textContent.trim()));
    fireEvent.click(pairButton);

    await waitFor(() => expect(screen.getByText(RATE_LIMITED_MESSAGE)).toBeTruthy());
    expect(callMock).toHaveBeenCalledTimes(1);
    expect(callMock.mock.calls[0][1]).toBe('host.connections.exchange_pairing');
    expect(document.querySelector('[data-pair-input]').value).toBe(LINK);
    expect(screen.queryByText(/re-pair|Token rejected/i)).toBeNull();
  });
});
