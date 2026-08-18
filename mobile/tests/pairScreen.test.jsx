import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const { fontOf } = vi.hoisted(() => ({
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
    TextInput: () => React.createElement('input', {}),
  };
});

vi.mock('expo-camera', () => ({
  CameraView: () => null,
  useCameraPermissions: () => [{ granted: false }, vi.fn()],
}));
vi.mock('expo-clipboard', () => ({ getStringAsync: vi.fn(async () => '') }));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.3.1' } } }));
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn() }),
  useLocalSearchParams: () => ({}),
}));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));

vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', danger: '#f00', line: '#ddd', bgInput: '#fafafa' },
    fonts: {
      sans: { regular: 'Inter_400Regular', medium: 'Inter_500Medium', semibold: 'Inter_600SemiBold' },
      mono: 'JetBrainsMono_400Regular',
    },
    fontSizes: { xs: 11, md: 14, lg: 15, xl: 18, display: 28 },
    lineHeights: { normal: 1.5 },
    mobile: {},
  }),
}));

vi.mock('../src/components/Button', () => ({ Button: ({ title }) => React.createElement('button', { type: 'button' }, title) }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ addConnection: vi.fn() }) }));

import Pair from '../app/pair.jsx';

describe('Pair screen typography', () => {
  it('draws the back chevron and the heading in theme fonts', () => {
    render(<Pair />);
    expect(document.querySelector('svg')).toBeTruthy();
    expect(screen.getByText('Pair this phone').getAttribute('data-font')).toBe('Inter_600SemiBold');
  });
});
