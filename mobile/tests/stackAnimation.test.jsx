import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  window: { width: 393, height: 852 },
  pathname: '/',
  options: [],
  mounts: 0,
}));

vi.mock('react-native', () => ({
  View: ({ children }) => React.createElement('div', {}, children),
  ActivityIndicator: () => React.createElement('span', { 'data-spinner': 'true' }),
  Platform: { OS: 'ios', select: (sel) => sel?.ios ?? sel?.default },
  Keyboard: { addListener: () => ({ remove: () => {} }) },
  StyleSheet: { create: (s) => s },
  useWindowDimensions: () => h.window,
}));

vi.mock('expo-router', () => ({
  usePathname: () => h.pathname,
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn() }),
  Stack: ({ screenOptions }) => {
    h.options.push(screenOptions);
    React.useEffect(() => {
      h.mounts += 1;
    }, []);
    return React.createElement('div', { 'data-testid': 'stack' });
  },
}));

vi.mock('expo-font', () => ({ useFonts: () => [true] }));
vi.mock('expo-splash-screen', () => ({
  preventAutoHideAsync: vi.fn(async () => {}),
  hideAsync: vi.fn(async () => {}),
}));
vi.mock('expo-status-bar', () => ({ StatusBar: () => React.createElement('span', {}) }));
vi.mock('@expo-google-fonts/geist', () => ({
  Geist_400Regular: 'g400', Geist_500Medium: 'g500', Geist_600SemiBold: 'g600', Geist_700Bold: 'g700',
}));
vi.mock('@expo-google-fonts/inter', () => ({
  Inter_400Regular: 'i400', Inter_500Medium: 'i500', Inter_600SemiBold: 'i600', Inter_700Bold: 'i700',
}));
vi.mock('@expo-google-fonts/jetbrains-mono', () => ({
  JetBrainsMono_400Regular: 'j400', JetBrainsMono_500Medium: 'j500', JetBrainsMono_600SemiBold: 'j600',
}));
vi.mock('react-native-gesture-handler', () => ({
  GestureHandlerRootView: ({ children }) => React.createElement('div', {}, children),
}));
vi.mock('react-native-safe-area-context', () => ({
  SafeAreaProvider: ({ children }) => React.createElement('div', {}, children),
}));

vi.mock('../src/theme/ThemeContext', () => ({
  ThemeProvider: ({ children }) => React.createElement('div', {}, children),
  useTheme: () => ({ mode: 'light', colors: { bg: '#fff', bgPane: '#fff', line: '#eee', ink2: '#333' } }),
}));
vi.mock('../src/components/Toast', () => ({
  ToastProvider: ({ children }) => React.createElement('div', {}, children),
  useToast: () => vi.fn(),
}));
vi.mock('../src/features/approval/ApprovalSheet', () => ({ ApprovalSheet: () => null }));
vi.mock('../src/features/clarification/ClarificationSheet', () => ({ ClarificationSheet: () => null }));
vi.mock('../src/features/aln/deeplink', () => ({ useNotificationTapRouter: () => {} }));
vi.mock('../src/features/shell/SidebarPane', () => ({
  SidebarPane: () => React.createElement('div', { 'data-testid': 'sidebar' }),
}));
vi.mock('../src/hooks/useEvents', () => ({ EventsProvider: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/hooks/useScheduleToast', () => ({ useScheduleToast: () => {} }));
vi.mock('../src/lib/AppBootstrap', () => ({ AppBootstrap: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({ activeId: 'e1', forget: vi.fn(), connections: [], markConnectionStatus: vi.fn() }),
}));
vi.mock('../src/lib/EndpointProvider', () => ({
  EndpointProvider: ({ children }) => React.createElement('div', {}, children),
}));
vi.mock('../src/lib/rpc', () => ({ setAuthFailedHandler: vi.fn() }));

import RootLayout from '../app/_layout.jsx';

const PHONE = { width: 393, height: 852 };
const TABLET = { width: 834, height: 1194 };

function lastOptions() {
  return h.options[h.options.length - 1];
}

function stackNode(container) {
  return container.querySelector('[data-testid="stack"]');
}

beforeEach(() => {
  h.window = PHONE;
  h.pathname = '/';
  h.options = [];
  h.mounts = 0;
});

describe('root layout screenOptions', () => {
  it('slides the pane in on a phone', () => {
    render(<RootLayout />);
    expect(lastOptions().animation).toBe('slide_from_right');
  });

  it('drops the animation on a tablet', () => {
    h.window = TABLET;
    render(<RootLayout />);
    expect(lastOptions().animation).toBe('none');
  });

  it('keeps the slide on a tablet route that stays single-pane', () => {
    h.window = TABLET;
    h.pathname = '/pair';
    render(<RootLayout />);
    expect(lastOptions().animation).toBe('slide_from_right');
  });

  it('stops blurred screens re-rendering behind the transition, in both pane modes', () => {
    render(<RootLayout />);
    expect(lastOptions().freezeOnBlur).toBe(true);
    cleanup();
    h.window = TABLET;
    render(<RootLayout />);
    expect(lastOptions().freezeOnBlur).toBe(true);
  });

  it('hands the navigator one stable options object across redundant renders', () => {
    render(<RootLayout />);
    const { rerender } = render(<RootLayout />);
    const before = lastOptions();
    rerender(<RootLayout />);
    expect(lastOptions()).toBe(before);
  });

  it('flips the animation without remounting the navigator', () => {
    h.window = TABLET;
    const { container, rerender } = render(<RootLayout />);
    const node = stackNode(container);
    expect(lastOptions().animation).toBe('none');
    expect(h.mounts).toBe(1);

    for (const [window, animation] of [
      [PHONE, 'slide_from_right'],
      [TABLET, 'none'],
      [{ width: 1194, height: 834 }, 'none'],
      [PHONE, 'slide_from_right'],
    ]) {
      h.window = window;
      rerender(<RootLayout />);
      expect(lastOptions().animation).toBe(animation);
      expect(stackNode(container)).toBe(node);
      expect(h.mounts).toBe(1);
    }
  });
});
