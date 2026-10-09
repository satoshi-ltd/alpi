import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const { fontOf, h } = vi.hoisted(() => ({
  h: { params: {}, replace: vi.fn(), spent: false, remember: vi.fn(), probe: { status: 'online', deviceId: 'd1', deviceName: 'Mac', role: 'admin', summaries: [] } },
  fontOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((f, s) => s.fontFamily ?? f, null),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) =>
    React.createElement('span', { ...p, 'data-font': fontOf(style) }, children);
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
    TextInput: ({ value }) => React.createElement('input', { value: value ?? '', readOnly: true }),
  };
});

vi.mock('expo-camera', () => ({
  CameraView: () => null,
  useCameraPermissions: () => [{ granted: false }, vi.fn()],
}));
vi.mock('expo-clipboard', () => ({ getStringAsync: vi.fn(async () => '') }));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.3.1' } } }));
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: h.replace, canGoBack: () => true }),
  usePathname: () => '/pair',
  useLocalSearchParams: () => h.params,
}));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));

vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', danger: '#f00', line: '#ddd', bgInput: '#fafafa' },
    fonts: {
      sans: { regular: 'Geist_400Regular', medium: 'Geist_500Medium', semibold: 'Geist_600SemiBold' },
      mono: 'GeistMono_400Regular',
    },
    fontSizes: { xs: 11, md: 14, lg: 15, xl: 18, display: 28 },
    lineHeights: { normal: 1.5 },
    mobile: {},
  }),
}));

vi.mock('../src/components/Button', () => ({ Button: ({ title, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, title) }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ addConnection: vi.fn() }) }));

vi.mock('../src/lib/spentPairings', () => ({ isSpentPairing: async () => h.spent, rememberSpentPairing: h.remember }));
vi.mock('../src/lib/pairing', async (importOriginal) => ({ ...(await importOriginal()), exchangePairing: async (endpoint) => { const { pairingToken: _used, ...rest } = endpoint; return rest; } }));
vi.mock('../src/lib/probe', () => ({ probe: async () => h.probe }));
vi.mock('../src/lib/rpc', () => ({ call: async () => ({}) }));

import Pair from '../app/pair.jsx';

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

  it('leaves for the inbox when the system hands the same link over again after it was used', async () => {
    h.params = LINK;
    h.spent = true;
    h.replace.mockClear();
    render(<Pair />);
    await waitFor(() => expect(h.replace).toHaveBeenCalledWith('/'));
    expect(document.querySelector('input').value).toBe('');
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
