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
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, numberOfLines, ellipsizeMode, style, ...p }) =>
    React.createElement('span', p, children);
  const Pressable = ({ children, onPress, onLongPress, android_ripple, style, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, onDoubleClick: onLongPress, ...p },
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
    setMode: vi.fn(),
    colors: { bgPane: '#fff', bgInput: '#eee', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', line: '#eee', selected: '#eee', danger: '#c00' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoMedium: 'monoMedium' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15, xl: 18 },
    textScale: h.textScale,
    setTextScale: h.setTextScale,
  }),
}));

vi.mock('../../components/OnOff', () => ({
  OnOff: ({ on, onLabel, offLabel }) =>
    React.createElement('span', { 'data-onoff': on ? onLabel : offLabel }),
}));
vi.mock('../../components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../../components/TypedConfirm', () => ({
  Bold: ({ children }) => React.createElement('span', {}, children),
  Code: ({ children }) => React.createElement('span', {}, children),
  TypedConfirm: ({ open, onConfirm }) =>
    open ? React.createElement('button', { type: 'button', 'data-confirm': 'sign-out', onClick: onConfirm }) : null,
}));
vi.mock('../../lib/biometric', () => ({
  authenticate: vi.fn(async () => true),
  biometricCapabilities: h.caps,
  getBiometricPref: h.pref,
  setBiometricPref: vi.fn(async () => {}),
}));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ unpair: h.unpair }) }));
vi.mock('../../lib/signOut', () => ({ signOut: h.signOut }));
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

  it('names the theme preference without leaking the resolved colour', async () => {
    render(<SettingsBody />);
    await waitFor(() => expect(screen.getByText('Face ID unlock')).toBeTruthy());
    expect(screen.getByText('System')).toBeTruthy();
    expect(screen.queryByText(/System \(/)).toBeNull();
    expect(screen.queryByText(/dark/i)).toBeNull();
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

function stepper(label) {
  return document.querySelector(`[accessibilityLabel="${label}"]`);
}

describe('SettingsBody text size', () => {
  it('names the current step next to the label', () => {
    h.textScale = 1.15;
    render(<SettingsBody />);
    expect(screen.getByText('Text size')).toBeTruthy();
    expect(screen.getByText('Large')).toBeTruthy();
  });

  it('steps up and down one notch per press', () => {
    render(<SettingsBody />);
    fireEvent.click(stepper('Larger text'));
    expect(h.setTextScale).toHaveBeenCalledWith(1.15);
    h.setTextScale.mockClear();
    fireEvent.click(stepper('Smaller text'));
    expect(h.setTextScale).toHaveBeenCalledWith(0.9);
  });

  it('disables the step that would run off the end of the scale', () => {
    h.textScale = MAX_TEXT_SCALE;
    const { rerender } = render(<SettingsBody />);
    expect(stepper('Larger text').disabled).toBe(true);
    expect(stepper('Smaller text').disabled).toBe(false);

    h.textScale = MIN_TEXT_SCALE;
    rerender(<SettingsBody />);
    expect(stepper('Smaller text').disabled).toBe(true);
    expect(stepper('Larger text').disabled).toBe(false);
  });

  it('resets to the default on a long press, mirroring desktop cmd-0', () => {
    h.textScale = MAX_TEXT_SCALE;
    render(<SettingsBody />);
    fireEvent.doubleClick(screen.getByText('Text size').closest('button'));
    expect(h.setTextScale).toHaveBeenCalledWith(1);
  });

  it('renders without a theme that knows about text size', () => {
    h.textScale = undefined;
    render(<SettingsBody />);
    expect(screen.getByText('Default')).toBeTruthy();
    expect(stepper('Smaller text').disabled).toBe(false);
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
