import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

vi.stubGlobal('__DEV__', false);

const h = vi.hoisted(() => ({
  role: 'admin',
  pathname: '/settings',
  back: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  canGoBack: vi.fn(() => true),
  call: vi.fn(async () => ({})),
  unpair: vi.fn(async () => {}),
  signOut: vi.fn(async () => {}),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, numberOfLines, ellipsizeMode, style, ...p }) =>
    React.createElement('span', p, children);
  const Pressable = ({ children, onPress, hitSlop, android_ripple, style, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...p }, children);
  const ScrollView = ({ children, contentContainerStyle, ...p }) => React.createElement('div', p, children);
  return { View, Text, Pressable, ScrollView, StyleSheet: { create: (s) => s } };
});

vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.3.1' } } }));

vi.mock('expo-router', () => ({
  usePathname: () => h.pathname,
  useRouter: () => ({ back: h.back, replace: h.replace, canGoBack: h.canGoBack, push: h.push }),
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
}));

vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    pref: 'system',
    mode: 'dark',
    setMode: vi.fn(),
    colors: {
      bg: '#fff', bgPane: '#fff', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999',
      line: '#eee', selected: '#eaeaea', danger: '#c00',
    },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoMedium: 'monoMedium' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15, xl: 18 },
  }),
}));

vi.mock('../src/components/Icon', () => ({
  Icon: ({ name }) => React.createElement('span', { 'data-icon': name }),
}));
vi.mock('../src/components/OnOff', () => ({
  OnOff: ({ on, onLabel, offLabel }) =>
    React.createElement('span', { 'data-onoff': on ? onLabel : offLabel }),
}));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../src/components/TypedConfirm', () => ({
  Bold: ({ children }) => React.createElement('span', {}, children),
  Code: ({ children }) => React.createElement('span', {}, children),
  TypedConfirm: ({ open, onConfirm }) =>
    open ? React.createElement('button', { type: 'button', 'data-confirm': 'sign-out', onClick: onConfirm }) : null,
}));

vi.mock('../src/lib/biometric', () => ({
  authenticate: vi.fn(async () => true),
  biometricCapabilities: vi.fn(async () => ({ hasHardware: true, enrolled: true, label: 'Face ID' })),
  getBiometricPref: vi.fn(async () => false),
  setBiometricPref: vi.fn(async () => {}),
}));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({ unpair: h.unpair, call: h.call, activeRole: h.role }),
}));
vi.mock('../src/lib/signOut', () => ({ signOut: h.signOut }));
vi.mock('../src/features/aln/notify', () => ({
  getPermissionStatus: vi.fn(async () => 'granted'),
  requestPermission: vi.fn(async () => 'granted'),
}));

vi.mock('../src/hooks/useActiveRole', () => ({
  useActiveRole: () => h.role,
  useCanAdminEarly: () => h.role !== 'member',
  useIsAdmin: () => h.role === 'admin',
}));

import { PaneContext } from '../src/nav/PaneContext';
import SettingsScreen from '../app/settings.jsx';

function mount(twoPane) {
  const node = <SettingsScreen />;
  if (!twoPane) return render(node);
  return render(
    <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>{node}</PaneContext.Provider>,
  );
}

function row(label) {
  return screen.getByText(label).closest('button');
}

function chevron() {
  return document.querySelector('[data-icon="back"]');
}

beforeEach(() => {
  h.role = 'admin';
  h.pathname = '/settings';
  h.back.mockClear();
  h.push.mockClear();
  h.replace.mockClear();
  h.call.mockClear();
  h.unpair.mockClear();
  h.signOut.mockClear();
  h.canGoBack.mockClear().mockReturnValue(true);
});

describe('settings route', () => {
  it('renders the device rows the sheet used to own', async () => {
    mount(true);
    expect(screen.getByText('Settings')).toBeTruthy();
    await waitFor(() => expect(screen.getByText('Face ID unlock')).toBeTruthy());
    for (const label of ['Re-pair this phone', 'System permission', 'Theme', 'Sign out']) {
      expect(screen.getByText(label)).toBeTruthy();
    }
  });

  it('renders before the role probe settles — nothing here needs a role', () => {
    h.role = null;
    mount(false);
    expect(screen.getByText('Sign out')).toBeTruthy();
    expect(h.back).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
  });
});

describe('settings route · member', () => {
  beforeEach(() => {
    h.role = 'member';
  });

  it('lets a member in instead of bouncing them back', () => {
    mount(false);
    expect(screen.getByText('Sign out')).toBeTruthy();
    expect(h.back).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalledWith('/');
  });

  it('keeps sign out reachable for a member', async () => {
    mount(false);
    fireEvent.click(row('Sign out'));
    fireEvent.click(document.querySelector('[data-confirm="sign-out"]'));
    await waitFor(() => expect(h.replace).toHaveBeenCalledWith('/onboarding'));
    expect(h.signOut).toHaveBeenCalled();
    expect(h.unpair).toHaveBeenCalled();
  });

  it('shows a member only device-personal sections', async () => {
    mount(false);
    await waitFor(() => expect(screen.getByText('Face ID unlock')).toBeTruthy());
    for (const section of ['This phone', 'Notifications', 'Appearance', 'Danger zone', 'About']) {
      expect(screen.getByText(section)).toBeTruthy();
    }
    expect(screen.queryByText('Test notifications')).toBeNull();
  });

  it('fires no daemon call from any row a member can press', async () => {
    mount(false);
    await waitFor(() => expect(screen.getByText('Face ID unlock')).toBeTruthy());
    for (const button of document.querySelectorAll('button')) fireEvent.click(button);
    expect(h.call).not.toHaveBeenCalled();
  });
});

describe('settings route back chevron', () => {
  it('shows no chevron as a pane beside the sidebar — nothing sits behind it', () => {
    mount(true);
    expect(chevron()).toBeNull();
  });

  it('keeps the chevron on the phone screen', () => {
    mount(false);
    expect(chevron()).toBeTruthy();
  });
});
