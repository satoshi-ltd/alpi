import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  call: vi.fn(async () => ({})),
  summary: null,
  refresh: vi.fn(async () => null),
  params: { id: 'conn_1' },
  endpoint: { id: 'phone-conn', deviceId: 'dev_me' },
  push: vi.fn(),
  replace: vi.fn(),
  toast: vi.fn(),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, onLayout, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, numberOfLines, ellipsizeMode, selectable, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, onLongPress, style, hitSlop, android_ripple, accessibilityRole, accessibilityLabel, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, ...p }, children);
  return {
    View,
    Text,
    Pressable,
    ScrollView: ({ children, contentContainerStyle, keyboardShouldPersistTaps, ...p }) => React.createElement('div', p, children),
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'spinner' }),
    Share: { share: vi.fn(async () => ({})) },
    StyleSheet: { create: (s) => s },
    TextInput: ({ value, onChangeText, placeholder, style, ...p }) =>
      React.createElement('input', { value, placeholder, onChange: (e) => onChangeText?.(e.target.value) }),
  };
});

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
}));

vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, replace: h.replace, back: vi.fn(), canGoBack: () => true }),
  useLocalSearchParams: () => h.params,
  usePathname: () => '/connections',
  useFocusEffect: (fn) => { fn?.(); },
}));

vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      bg: '#fff', bgPane: '#fff', bgInput: '#f1f3f5', line: '#eee', line2: '#ddd', selected: '#eaeaea',
      ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', accent: '#c90',
      danger: '#c00', dangerText: '#b00', warning: '#dd0', success: '#0a0',
    },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoMedium: 'monoMedium', monoSemibold: 'monoSemibold' },
    fontSizes: { xxs: 9, label: 10, xs: 11, sm: 12, md: 14, lg: 15, xl: 18, display: 28 },
    mobile: { tap: 44, inputH: 44, btnH: 48 },
  }),
}));

vi.mock('../src/components/AdminGuard', () => ({ AdminGuard: ({ children }) => children }));
vi.mock('../src/components/Button', () => ({ Button: ({ title, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, title) }));
vi.mock('../src/components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../src/components/ScreenHeader', () => ({ ScreenHeader: ({ title, right }) => React.createElement('h1', {}, title, right) }));
vi.mock('../src/components/SyncBar', () => ({ SyncBar: () => null }));
vi.mock('../src/components/TextPrompt', () => ({ TextPrompt: () => null }));
vi.mock('../src/components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../src/components/UsageChart', () => ({ UsageChart: () => React.createElement('div', { 'data-chart': 'true' }) }));
vi.mock('../src/components/ActionSheet', () => ({
  ActionSheet: ({ open, actions = [] }) =>
    open
      ? React.createElement('div', { 'data-sheet': 'add' }, actions.map((a) =>
          React.createElement('button', { key: a.id, type: 'button', onClick: a.onPress }, a.label)))
      : null,
}));
vi.mock('../src/components/Sheet', () => ({
  Sheet: ({ open, title, children, primaryAction }) =>
    open
      ? React.createElement('div', { 'data-sheet': title }, children,
          primaryAction ? React.createElement('button', { type: 'button', onClick: primaryAction.onPress, disabled: primaryAction.disabled }, primaryAction.label) : null)
      : null,
}));
vi.mock('../src/components/TypedConfirm', () => ({
  Bold: ({ children }) => React.createElement('b', {}, children),
  Code: ({ children }) => React.createElement('code', {}, children),
  TypedConfirm: ({ open, title, onConfirm }) =>
    open ? React.createElement('button', { type: 'button', 'data-confirm': title, onClick: onConfirm }, 'confirm') : null,
}));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => vi.fn() }));
vi.mock('../src/hooks/useDaemonData', () => ({
  useConnectionsSummary: () => ({ data: h.summary, loading: false, error: null, refresh: h.refresh }),
  useProfileSummaries: () => ({ data: { profiles: [{ name: 'doc' }, { name: 'abby' }] }, loading: false, refresh: vi.fn() }),
}));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({ call: h.call, activeId: 'phone-conn', endpoint: h.endpoint }),
}));

import ConnectionsRoute from '../app/connections/index.jsx';
import ConnectionRoute from '../app/connections/[id].jsx';

const SUMMARY = {
  connections: [
    { id: 'host', label: 'Host', role: 'admin', status: 'active', profile_scope: [], devices: [], sessions: 12, last_seen: null, cost_14d: 1.5, tokens_14d: 100, usage_days: [] },
    {
      id: 'conn_1', label: 'Support', role: 'member', status: 'active', profile_scope: ['doc'], session_scope: 'connection',
      sessions: 3, last_seen: null, cost_14d: 0.42, tokens_14d: 100, usage_days: [{ iso: '2026-09-28', tokIn: 10, tokOut: 5, cost: 0.42 }],
      devices: [
        { id: 'dev_a', name: 'Pixel', client: 'mobile', app_version: '0.5.0', status: 'active', last_seen: null, provisioner: false, expired: false },
        { id: 'dev_b', name: 'server', client: 'web', app_version: '1.0', status: 'active', last_seen: null, provisioner: true, expired: false },
      ],
    },
    { id: 'conn_2', label: 'Off', role: 'admin', status: 'disabled', profile_scope: [], devices: [], sessions: 0, last_seen: null, cost_14d: 0, tokens_14d: 0, usage_days: [] },
  ],
};

beforeEach(() => {
  h.call.mockClear().mockResolvedValue({ ok: true });
  h.refresh.mockClear();
  h.push.mockClear();
  h.replace.mockClear();
  h.summary = SUMMARY;
  h.params = { id: 'conn_1' };
  h.endpoint = { id: 'phone-conn', deviceId: 'dev_me' };
});

describe('connections list', () => {
  it('lists paired connections with role, scope and device count, and the host apart', () => {
    render(<ConnectionsRoute />);
    expect(screen.getByText('Support')).toBeTruthy();
    expect(screen.getByText('member · doc · 2 devices · 3 sessions · seen never')).toBeTruthy();
    expect(screen.getByText('disabled')).toBeTruthy();
    expect(screen.getByText('Local host')).toBeTruthy();
    expect(screen.getByText('12 sessions · seen never')).toBeTruthy();
    const host = screen.getByText('Local host');
    const first = screen.getByText('Support');
    expect(Boolean(host.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it('opens a connection on press', () => {
    render(<ConnectionsRoute />);
    fireEvent.click(screen.getByText('Support'));
    expect(h.push).toHaveBeenCalledWith('/connections/conn_1');
  });

  it('creates a connection from the sheet and hands its grant to the pairing sheet', async () => {
    h.call.mockImplementation(async (method) =>
      method === 'host.connections.create'
        ? { connection_id: 'conn_9', pairing_id: 'pair_1', pairing_token: 'tok', pairing_status: 'pending', label: 'Web', role: 'member', endpoints: [{ url: 'ws://10.0.0.2:49200', label: 'lan' }] }
        : { status: 'pending' });
    render(<ConnectionsRoute />);
    fireEvent.click(screen.getByText('New'));
    fireEvent.click(screen.getByLabelText('Include @doc'));
    fireEvent.click(screen.getByText('Sessions private per device'));
    const input = document.querySelector('input');
    fireEvent.change(input, { target: { value: 'Web' } });
    fireEvent.click(screen.getByText('Create + pair'));
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.connections.create', {
      label: 'Web', role: 'member', profiles: ['doc'], session_scope: 'device',
    }));
    await waitFor(() => expect(screen.getByText(/alpi:\/\/device\?url=ws%3A%2F%2F10\.0\.0\.2%3A49200/)).toBeTruthy());
    expect(h.refresh).toHaveBeenCalled();
  });
});

describe('connection detail', () => {
  it('shows devices with their flags and this phone marked', () => {
    h.params = { id: 'conn_1' };
    render(<ConnectionRoute />);
    expect(screen.getByText('Pixel')).toBeTruthy();
    expect(screen.getByText('web · 1.0 · never · provisioner')).toBeTruthy();
    expect(screen.getByText('per connection')).toBeTruthy();
    expect(document.querySelector('[data-chart]')).toBeTruthy();
  });

  it('revokes a device after the typed confirmation', async () => {
    render(<ConnectionRoute />);
    fireEvent.click(screen.getByLabelText('Revoke Pixel'));
    fireEvent.click(screen.getByText('confirm'));
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.connections.revoke_device', { connection_id: 'conn_1', device_id: 'dev_a' }));
    expect(h.refresh).toHaveBeenCalled();
  });

  it('flips the session scope through update', async () => {
    render(<ConnectionRoute />);
    fireEvent.click(screen.getByText('Session scope'));
    fireEvent.click(screen.getByText('confirm'));
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.connections.update', { connection_id: 'conn_1', session_scope: 'device' }));
  });

  it('disables another connection on a plain tap', async () => {
    render(<ConnectionRoute />);
    fireEvent.click(screen.getByText('Disable connection'));
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.connections.set_status', { connection_id: 'conn_1', status: 'disabled' }));
  });

  it('asks for a typed confirmation before disabling the connection this phone is paired through', async () => {
    h.endpoint = { id: 'phone-conn', connectionId: 'conn_1', deviceId: 'dev_me' };
    render(<ConnectionRoute />);
    expect(screen.getByText('this phone goes offline with it · an admin elsewhere must re-enable it')).toBeTruthy();
    fireEvent.click(screen.getByText('Disable connection'));
    expect(h.call).not.toHaveBeenCalledWith('host.connections.set_status', expect.anything());
    fireEvent.click(screen.getByText('confirm'));
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.connections.set_status', { connection_id: 'conn_1', status: 'disabled' }));
  });

  it('marks this phone by the device id the daemon issued, not by the daemon identity', () => {
    h.endpoint = { id: 'phone-conn', deviceId: 'dev_a', ownDeviceId: 'dev_b' };
    render(<ConnectionRoute />);
    expect(screen.getByText('this phone')).toBeTruthy();
    expect(screen.getByText('this phone goes offline with it · an admin elsewhere must re-enable it')).toBeTruthy();
  });

  it('recognises this phone by the daemon connection id, not the local endpoint id', () => {
    h.endpoint = { id: 'conn_1', deviceId: 'dev_me' };
    render(<ConnectionRoute />);
    expect(screen.queryByText('this phone goes offline with it · an admin elsewhere must re-enable it')).toBeNull();
  });

  it('mints a provisioning grant from the add-device sheet', async () => {
    h.call.mockImplementation(async (method) =>
      method === 'host.connections.add_device'
        ? { connection_id: 'conn_1', pairing_id: 'pair_2', pairing_token: 'tok2', pairing_status: 'pending', label: 'Support', url: 'ws://h:1' }
        : { status: 'pending' });
    render(<ConnectionRoute />);
    fireEvent.click(screen.getByText('+ Add device'));
    fireEvent.click(screen.getByText('Provisioning link'));
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.connections.add_device', { connection_id: 'conn_1', provisioner: true }));
    await waitFor(() => expect(screen.getByText(/pairing_token=tok2/)).toBeTruthy());
  });

  it('deletes the connection and returns to the list', async () => {
    render(<ConnectionRoute />);
    fireEvent.click(screen.getByText('Delete connection'));
    fireEvent.click(screen.getByText('confirm'));
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.connections.delete', { connection_id: 'conn_1' }));
    await waitFor(() => expect(h.replace).toHaveBeenCalledWith('/connections'));
  });

  it('keeps the host row read-only', () => {
    h.params = { id: 'host' };
    render(<ConnectionRoute />);
    expect(screen.getByText('Local host')).toBeTruthy();
    expect(screen.queryByText('+ Add device')).toBeNull();
    expect(screen.queryByText('Delete connection')).toBeNull();
  });
});
