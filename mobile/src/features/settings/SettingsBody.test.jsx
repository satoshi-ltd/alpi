import React from 'react';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

vi.stubGlobal('__DEV__', false);

const h = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  caps: vi.fn(async () => ({ hasHardware: true, enrolled: true, label: 'Face ID' })),
  pref: vi.fn(async () => false),
  permission: vi.fn(async () => 'granted'),
  signOut: vi.fn(async () => {}),
  unpair: vi.fn(async () => {}),
  textScale: 1,
  setTextScale: vi.fn(),
  setMode: vi.fn(),
  health: null,
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, numberOfLines, ellipsizeMode, style, ...p }) =>
    React.createElement('span', p, children);
  const Pressable = ({ children, onPress, onLongPress, android_ripple, style, accessibilityState, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, onDoubleClick: onLongPress, 'aria-checked': accessibilityState?.selected, ...p },
      children,
    );
  const ScrollView = ({ children, contentContainerStyle, ...p }) =>
    React.createElement('div', { 'data-scroll': 'true', ...p }, children);
  return { View, Text, Pressable, ScrollView, StyleSheet: { create: (s) => s } };
});

vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.3.1' } } }));
vi.mock('expo-router', () => ({ useRouter: () => ({ push: h.push, replace: h.replace }) }));

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    pref: 'system',
    mode: 'dark',
    setMode: h.setMode,
    colors: { bg: '#fff', accent: '#8a5a0a', bgPane: '#fff', field: '#eee', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', line: '#eee', selected: '#eee', danger: '#c00' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoMedium: 'monoMedium' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15, xl: 18 },
    textScale: h.textScale,
    setTextScale: h.setTextScale,
  }),
}));

vi.mock('../../lib/haptics', () => ({ selection: vi.fn() }));
vi.mock('../../components/Toggle', () => ({
  Toggle: ({ on, disabled, label, onChange }) =>
    React.createElement('input', { type: 'checkbox', 'data-toggle': label, checked: !!on, disabled: !!disabled, onChange: (e) => onChange?.(e.target.checked) }),
}));
vi.mock('../../components/Pill', () => ({
  Pill: ({ children, tone }) => React.createElement('span', { 'data-pill': tone ?? '' }, children),
}));
vi.mock('../../components/OnOff', () => ({
  OnOff: ({ on, onLabel, offLabel }) =>
    React.createElement('span', { 'data-onoff': on ? onLabel : offLabel }),
}));
vi.mock('../../components/Fold', () => ({
  Fold: ({ fold, color, size }) => React.createElement('span', { 'data-fold': fold, 'data-color': color ?? '', 'data-size': size }),
}));
vi.mock('../../components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../../components/ConfirmDialog', () => ({
  Bold: ({ children }) => React.createElement('span', {}, children),
  Code: ({ children }) => React.createElement('span', {}, children),
  ConfirmDialog: ({ open, onConfirm }) =>
    open ? React.createElement('button', { type: 'button', 'data-confirm': 'sign-out', onClick: onConfirm }) : null,
}));
vi.mock('../../lib/biometric', () => ({
  authenticate: vi.fn(async () => true),
  biometricCapabilities: h.caps,
  getBiometricPref: h.pref,
  setBiometricPref: vi.fn(async () => {}),
}));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ unpair: h.unpair, activeRole: h.role ?? null }) }));
vi.mock('../../lib/signOut', () => ({ signOut: h.signOut }));
vi.mock('../aln/health', () => ({
  readHealth: async () => h.health,
  describeHealth: (health) => health,
}));
vi.mock('../aln/notify', () => ({
  getPermissionStatus: h.permission,
  requestPermission: vi.fn(async () => 'granted'),
}));

import { MAX_TEXT_SCALE, MIN_TEXT_SCALE } from '../../theme/textScale';
import { SettingsBody } from './SettingsBody';

function rowButton(label) {
  return screen.getByText(label).closest('button');
}

beforeEach(() => {
  h.push.mockClear();
  h.replace.mockClear();
  h.caps.mockClear();
  h.signOut.mockClear();
  h.unpair.mockClear();
  h.textScale = 1;
  h.setTextScale.mockClear();
  h.setMode.mockClear();
  h.health = null;
});

describe('SettingsBody', () => {
  it('renders every device row the sheet used to own', async () => {
    render(<SettingsBody />);
    await waitFor(() => expect(screen.getByText('Face ID unlock')).toBeTruthy());
    for (const label of ['Re-pair this phone', 'System permission', 'Theme', 'Sign out']) {
      expect(screen.getByText(label)).toBeTruthy();
    }
    expect(screen.getByText('Alpi mobile · v0.3.1')).toBeTruthy();
  });

  it('signs the About block with the alpaca and a crease wordmark', async () => {
    render(<SettingsBody />);
    await waitFor(() => expect(screen.getByText('Face ID unlock')).toBeTruthy());
    expect(document.querySelectorAll('text')).toHaveLength(1);
    expect(document.querySelector('text').textContent).toBe('alpi');
    expect(document.querySelectorAll('linearGradient')).toHaveLength(1);
    const mark = document.querySelector('[data-fold]');
    expect(mark.getAttribute('data-fold')).toBe('alpaca');
    expect(mark.getAttribute('data-color')).toBe('');
  });

  it('names the theme preference without leaking the resolved colour', async () => {
    render(<SettingsBody />);
    await waitFor(() => expect(screen.getByText('Face ID unlock')).toBeTruthy());
    expect(radio('System').getAttribute('aria-checked')).toBe('true');
    expect(screen.queryByText(/System \(/)).toBeNull();
  });

  it('reads device state only while it is the visible surface', () => {
    const { rerender } = render(<SettingsBody active={false} />);
    expect(h.caps).not.toHaveBeenCalled();
    rerender(<SettingsBody active />);
    expect(h.caps).toHaveBeenCalled();
  });

  it('dismisses its host before navigating away', () => {
    const onDismiss = vi.fn();
    render(<SettingsBody onDismiss={onDismiss} />);
    fireEvent.click(rowButton('Re-pair this phone'));
    expect(onDismiss).toHaveBeenCalled();
    expect(h.push).toHaveBeenCalledWith('/pair');
  });

  it('navigates with no host to dismiss when it is the whole pane', () => {
    render(<SettingsBody />);
    fireEvent.click(rowButton('Re-pair this phone'));
    expect(h.push).toHaveBeenCalledWith('/pair');
  });

  it('signs out through the typed confirm', async () => {
    render(<SettingsBody />);
    fireEvent.click(rowButton('Sign out'));
    fireEvent.click(document.querySelector('[data-confirm="sign-out"]'));
    await waitFor(() => expect(h.replace).toHaveBeenCalledWith('/onboarding'));
    expect(h.signOut).toHaveBeenCalled();
    expect(h.unpair).toHaveBeenCalled();
  });
});

const radios = (group) => [...document.querySelector(`[accessibilityLabel="${group}"]`).querySelectorAll('[accessibilityRole="radio"]')];
const radio = (label) => document.querySelector(`[accessibilityRole="radio"][accessibilityLabel="${label}"]`);

describe('SettingsBody theme', () => {
  it('is a three-way segment, System then Light then Dark, with no chevron row', () => {
    render(<SettingsBody />);
    expect(radios('Theme').map((n) => n.getAttribute('accessibilityLabel'))).toEqual(['System', 'Light', 'Dark']);
  });

  it('applies the tapped mode', () => {
    render(<SettingsBody />);
    fireEvent.click(radio('Dark'));
    expect(h.setMode).toHaveBeenCalledWith('dark');
  });
});

describe('SettingsBody text size', () => {
  it('is a four-step segment under its label', () => {
    h.textScale = 1.15;
    render(<SettingsBody />);
    expect(radios('Text size').map((n) => n.getAttribute('accessibilityLabel'))).toEqual(['Small', 'Default', 'Large', 'Largest']);
    expect(radio('Large').getAttribute('aria-checked')).toBe('true');
    expect(screen.queryByLabelText('Larger text')).toBeNull();
    expect(document.querySelector('[accessibilityLabel="Smaller text"]')).toBeNull();
  });

  it('sets the tapped step', () => {
    render(<SettingsBody />);
    fireEvent.click(radio('Largest'));
    expect(h.setTextScale).toHaveBeenCalledWith(MAX_TEXT_SCALE);
    h.setTextScale.mockClear();
    fireEvent.click(radio('Small'));
    expect(h.setTextScale).toHaveBeenCalledWith(MIN_TEXT_SCALE);
  });

  it('keeps the helper to the OS multiplier, with no stepper hint', () => {
    render(<SettingsBody />);
    expect(screen.getByText('multiplies your OS text size')).toBeTruthy();
  });

  it('renders without a theme that knows about text size', () => {
    h.textScale = undefined;
    render(<SettingsBody />);
    expect(radio('Default').getAttribute('aria-checked')).toBe('true');
  });
});

describe('SettingsBody biometric', () => {
  const toggle = () => document.querySelector('[data-toggle="Face ID unlock"]');

  it('is a Toggle, not a tap-the-row pill', async () => {
    h.pref.mockResolvedValueOnce(true);
    render(<SettingsBody />);
    await waitFor(() => expect(toggle().checked).toBe(true));
    expect(rowButton('Face ID unlock')).toBeNull();
  });

  it('turns on after the biometric prompt and off without one', async () => {
    render(<SettingsBody />);
    await waitFor(() => expect(h.caps).toHaveBeenCalled());
    fireEvent.click(toggle());
    await waitFor(() => expect(toggle().checked).toBe(true));
    fireEvent.click(toggle());
    await waitFor(() => expect(toggle().checked).toBe(false));
  });

  it('disables the switch on a device with no biometric hardware', async () => {
    h.caps.mockResolvedValueOnce({ hasHardware: false, enrolled: false, label: 'Biometric' });
    render(<SettingsBody />);
    await waitFor(() => expect(document.querySelector('[data-toggle="Biometric unlock"]').disabled).toBe(true));
  });
});

describe('SettingsBody delivery status', () => {
  it('says blocked in the danger tone when delivery cannot work, instead of off', async () => {
    h.health = { ok: false, detail: 'Permission denied' };
    render(<SettingsBody />);
    await waitFor(() => expect(screen.getByText('blocked')).toBeTruthy());
    expect(screen.getByText('blocked').getAttribute('data-pill')).toBe('err');
  });

  it('keeps the on pill when delivery is healthy', async () => {
    h.health = { ok: true, detail: 'Last successful check just now.' };
    render(<SettingsBody />);
    await waitFor(() => expect(screen.getByText('Delivery status')).toBeTruthy());
    expect(screen.queryByText('blocked')).toBeNull();
  });
});

const ROOT = join(import.meta.dirname, '../../..');
const BODY = 'src/features/settings/SettingsBody.jsx';

function sourceFiles(dir) {
  return readdirSync(join(ROOT, dir), { withFileTypes: true }).flatMap((e) => {
    const rel = `${dir}/${e.name}`;
    if (e.isDirectory()) return sourceFiles(rel);
    return /\.jsx?$/.test(e.name) && !e.name.includes('.test.') ? [rel] : [];
  });
}

describe('one settings implementation', () => {
  it('app/settings.jsx renders the shared body instead of its own rows', () => {
    const source = readFileSync(join(ROOT, 'app/settings.jsx'), 'utf8');
    expect(source).toMatch(/import \{ SettingsBody \} from/);
    expect(source).toContain('<SettingsBody');
    expect(source).not.toContain('Re-pair this phone');
  });

  it.each(['opens QR scanner', 'Sign out of this phone?', 'instant while alpi is open'])(
    '“%s” exists in exactly one file',
    (needle) => {
      const owners = [...sourceFiles('src'), ...sourceFiles('app')].filter((path) =>
        readFileSync(join(ROOT, path), 'utf8').includes(needle),
      );
      expect(owners).toEqual([BODY]);
    },
  );
});

describe('daemon rows', () => {
  afterEach(() => {
    h.role = null;
  });

  it('hides connections and network from a member', async () => {
    h.role = 'member';
    render(<SettingsBody />);
    await waitFor(() => expect(screen.getByText('Face ID unlock')).toBeTruthy());
    expect(screen.queryByText('Connections')).toBeNull();
  });

  it('routes an admin to the connections screen', async () => {
    h.role = 'admin';
    render(<SettingsBody />);
    await waitFor(() => expect(screen.getByText('Connections')).toBeTruthy());
    fireEvent.click(rowButton('Connections'));
    expect(h.push).toHaveBeenCalledWith('/connections');
  });
});
