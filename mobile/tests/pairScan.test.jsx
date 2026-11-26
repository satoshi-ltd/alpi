import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';

afterEach(cleanup);

const memory = vi.hoisted(() => new Map());
vi.mock('expo-secure-store', () => ({
  getItemAsync: async (key) => (memory.has(key) ? memory.get(key) : null),
  setItemAsync: async (key, value) => { memory.set(key, value); },
  deleteItemAsync: async (key) => { memory.delete(key); },
}));

const h = vi.hoisted(() => ({
  connections: [],
  scanned: '',
  addConnection: vi.fn(),
  exchange: vi.fn(),
  probe: vi.fn(),
  call: vi.fn(),
  replace: vi.fn(),
}));

vi.mock('react-native', () => {
  const React = require('react');
  const box = ({ children, accessibilityRole }) => React.createElement('div', accessibilityRole === 'alert' ? { role: 'alert' } : {}, children);
  const TextInput = React.forwardRef(({ value, onChangeText, accessibilityLabel }, ref) =>
    React.createElement('textarea', { ref, value, 'aria-label': accessibilityLabel, onChange: (e) => onChangeText(e.target.value) }));
  return {
    View: box, ScrollView: box, Text: ({ children }) => React.createElement('span', {}, children), TextInput,
    AppState: { addEventListener: () => ({ remove() {} }) }, Keyboard: { dismiss() {} }, Linking: { openSettings() {} },
    Platform: { OS: 'ios', constants: { Model: 'phone' } },
  };
});
vi.mock('expo-camera', () => ({
  CameraView: ({ onBarcodeScanned }) => React.createElement('button', { type: 'button', onClick: () => onBarcodeScanned?.({ data: h.scanned }) }, 'camera'),
  useCameraPermissions: () => [{ granted: true }, vi.fn(), vi.fn()],
}));
vi.mock('expo-clipboard', () => ({ getStringAsync: async () => '' }));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '1.0.0' } } }));
vi.mock('expo-router', () => ({ useRouter: () => ({ replace: h.replace, canDismiss: () => false, dismissAll() {} }), useLocalSearchParams: () => ({ mode: 'scan' }) }));
vi.mock('../src/components/KeyboardPane', () => ({ KeyboardPane: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/tokens', () => ({ palettes: { dark: { ink: '#fff', ink3: '#999' } }, space: new Proxy({}, { get: () => 4 }) }));
vi.mock('../src/lib/firstRun', () => ({
  BUSY_MARK_PX: 40, busyMarkStyle: {}, firstRun: { gap: 8, stack: 8, tight: 4 }, firstRunActions: {}, firstRunColumn: {}, foldMarkStyle: {},
  firstRunBottom: () => ({}), firstRunScroll: () => ({}), firstRunType: () => new Proxy({}, { get: () => ({}) }),
}));
vi.mock('../src/components/Busy', () => ({ Busy: () => null }));
vi.mock('../src/components/Button', () => ({ Button: ({ title, onPress, disabled }) => React.createElement('button', { type: 'button', disabled: !!disabled, onClick: onPress }, title) }));
vi.mock('../src/components/Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('h3', {}, children) }));
vi.mock('../src/components/Fold', () => ({ Fold: () => null }));
vi.mock('../src/components/StepLadder', () => ({ StepLadder: () => null, ladderSteps: (steps) => steps }));
vi.mock('../src/components/well', () => ({ useWell: () => [{}, {}] }));
vi.mock('../src/hooks/useFirstRunLayout', () => ({ useFirstRunLayout: () => ({ edge: 16, insets: { top: 0, bottom: 0 } }), useKeyboardOpen: () => false }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ addConnection: h.addConnection, connections: h.connections }) }));
vi.mock('../src/lib/pairing', async (original) => ({ ...(await original()), exchangePairing: h.exchange }));
vi.mock('../src/components/ConfirmDialog', () => ({
  ConfirmDialog: ({ open, body, confirmLabel, onConfirm, onClose }) => (open ? React.createElement('div', { role: 'dialog' }, body,
    React.createElement('button', { type: 'button', onClick: onConfirm }, confirmLabel),
    React.createElement('button', { type: 'button', onClick: onClose }, 'Cancel')) : null),
}));
vi.mock('../src/lib/spentPairings', () => ({ isSpentPairing: async () => false, rememberSpentPairing: vi.fn() }));
vi.mock('../src/lib/probe', () => ({ probe: h.probe }));
vi.mock('../src/lib/rpc', () => ({ call: h.call }));
vi.mock('../src/theme/ThemeContext', () => {
  const React = require('react');
  const theme = { mode: 'light', colors: { bg: '#fff', ink: '#000', ink3: '#666', ink4: '#999' }, fonts: { sans: { regular: 'r', semibold: 's' } }, fontSizes: { xs: 12, sm: 13, md: 15 } };
  return { ThemeContext: React.createContext(theme), useTheme: () => theme };
});

import Pair from '../app/pair.jsx';
import { rememberSpentPairing } from '../src/lib/spentPairings';
import { loadConnections, saveConnection } from '../src/lib/store';

const code = (url, extra = {}) => JSON.stringify({ u: url, n: 'casa', g: 'one-time', ...extra });

async function scan(data) {
  h.scanned = data;
  render(<Pair />);
  await act(async () => { fireEvent.click(screen.getByText('camera')); });
}

beforeEach(() => {
  rememberSpentPairing.mockClear();
  h.connections = [{ id: 'c-1', url: 'ws://100.1.2.3:49200', deviceId: 'daemon-1', token: 'kept' }];
  for (const spy of [h.addConnection, h.exchange, h.probe, h.call, h.replace]) spy.mockReset();
  h.exchange.mockImplementation(async (endpoint) => ({ ...endpoint, token: 'device-token', deviceId: 'daemon-1' }));
  h.probe.mockResolvedValue({ status: 'online', deviceName: 'casa', deviceId: 'daemon-1', role: 'admin', summaries: [] });
  h.call.mockResolvedValue({});
});

describe('a scanned pairing code', () => {
  it('that carries a device token is refused before anything is asked of the daemon or saved', async () => {
    await scan(JSON.stringify({ u: 'ws://203.0.113.9:49200', n: 'evil', t: 'device-token' }));

    expect(screen.getByRole('alert').textContent).toContain('That code carries a device token');
    expect(screen.getByLabelText('alpi:// link').value).toBe('');
    expect(screen.queryByRole('dialog')).toBeNull();
    for (const spy of [h.exchange, h.probe, h.call, h.addConnection]) expect(spy).not.toHaveBeenCalled();
  });

  it('for a daemon this phone has no connection to spends nothing until the owner confirms', async () => {
    await scan(code('ws://203.0.113.9:49200'));

    expect(screen.getByRole('dialog').textContent).toContain('casa · ws://203.0.113.9:49200');
    for (const spy of [h.exchange, h.probe, h.call, h.addConnection]) expect(spy).not.toHaveBeenCalled();

    await act(async () => { fireEvent.click(within(screen.getByRole('dialog')).getByText('Pair')); });

    expect(h.exchange).toHaveBeenCalledTimes(1);
    expect(h.exchange.mock.calls[0][0]).toMatchObject({ url: 'ws://203.0.113.9:49200', pairingToken: 'one-time' });
    expect(h.addConnection).toHaveBeenCalledWith(expect.objectContaining({ url: 'ws://203.0.113.9:49200', deviceId: 'daemon-1' }));
  });

  it('that the owner declines is forgotten', async () => {
    await scan(code('ws://203.0.113.9:49200'));
    await act(async () => { fireEvent.click(screen.getByText('Cancel')); });

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByLabelText('alpi:// link').value).toBe('');
    expect(rememberSpentPairing).not.toHaveBeenCalled();
    expect(screen.queryByRole('alert')).toBeNull();
    for (const spy of [h.exchange, h.probe, h.call, h.addConnection]) expect(spy).not.toHaveBeenCalled();
  });

  it('for a host this phone is already paired with pairs at once', async () => {
    await scan(code('ws://100.1.2.3:49200'));

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(h.exchange).toHaveBeenCalledTimes(1);
    expect(h.addConnection).toHaveBeenCalledTimes(1);
  });
});

describe('a pairing that names a saved connection from another address', () => {
  const moved = code('ws://203.0.113.9:49200', { c: 'conn-1' });
  let before;

  beforeEach(async () => {
    memory.clear();
    before = await saveConnection({ name: 'casa', url: 'ws://100.1.2.3:49200', token: 'kept', deviceId: 'daemon-1', connectionId: 'conn-1' });
    h.connections = before.connections;
    h.exchange.mockImplementation(async (endpoint, _metadata, _rpc, onExchanged) => {
      const exchanged = { ...endpoint, token: 'device-token', deviceId: 'dev_this_phone' };
      await onExchanged(exchanged);
      return exchanged;
    });
    h.addConnection.mockImplementation((endpoint, options) => saveConnection(endpoint, options));
  });

  async function paste(data) {
    render(<Pair />);
    await act(async () => { fireEvent.click(screen.getByText('Paste link')); });
    await act(async () => { fireEvent.change(screen.getByLabelText('alpi:// link'), { target: { value: data } }); });
    await act(async () => { fireEvent.click(screen.getByText('Pair')); });
  }

  it('pasted, shows both addresses before anything is saved and changes nothing when the owner declines', async () => {
    await paste(moved);

    const dialog = screen.getByRole('dialog');
    expect(dialog.textContent).toContain('moves casa from ws://100.1.2.3:49200 to ws://203.0.113.9:49200');
    expect(await loadConnections()).toEqual(before);

    await act(async () => { fireEvent.click(within(dialog).getByText('Cancel')); });

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(await loadConnections()).toEqual(before);
    expect(h.probe).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
    expect(rememberSpentPairing).toHaveBeenCalledWith('one-time');
    expect(screen.getByRole('alert').textContent).toContain('Get a new pairing code from the host');
    expect(screen.getByLabelText('alpi:// link').value).toBe('');
    await act(async () => { fireEvent.click(screen.getByText('Use a new link')); });
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('pasted, moves that same connection once the owner agrees and adds no second one', async () => {
    await paste(moved);
    await act(async () => { fireEvent.click(within(screen.getByRole('dialog')).getByText('Move')); });

    expect(screen.queryByRole('dialog')).toBeNull();
    const after = await loadConnections();
    expect(after.connections).toHaveLength(1);
    expect(after.connections[0]).toMatchObject({
      id: before.connections[0].id, url: 'ws://203.0.113.9:49200', token: 'device-token', deviceId: 'daemon-1', connectionId: 'conn-1',
    });
    expect(after.active_id).toBe(before.active_id);
    expect(h.replace).toHaveBeenCalledWith(expect.objectContaining({ pathname: '/paired' }));
  });

  it('scanned, asks about the daemon first and about the move after it', async () => {
    await scan(moved);
    expect(screen.getByRole('dialog').textContent).toContain('This phone has no connection to the daemon in that code');
    await act(async () => { fireEvent.click(within(screen.getByRole('dialog')).getByText('Pair')); });

    expect(screen.getByRole('dialog').textContent).toContain('moves casa from ws://100.1.2.3:49200 to ws://203.0.113.9:49200');
    await act(async () => { fireEvent.click(within(screen.getByRole('dialog')).getByText('Cancel')); });

    expect(await loadConnections()).toEqual(before);
    expect(h.replace).not.toHaveBeenCalled();
    expect(screen.getByRole('alert').textContent).toContain('This code has been used');
  });

  it('at the address it already has replaces its sign-in in place, with no question', async () => {
    await paste(code('ws://100.1.2.3:49200', { c: 'conn-1' }));

    expect(screen.queryByRole('dialog')).toBeNull();
    const after = await loadConnections();
    expect(after.connections).toHaveLength(1);
    expect(after.connections[0]).toMatchObject({ id: before.connections[0].id, url: 'ws://100.1.2.3:49200', token: 'device-token', deviceId: 'daemon-1' });
  });

  it('for a connection this phone does not have adds one row beside the saved one', async () => {
    await paste(code('ws://203.0.113.9:49200', { c: 'conn-2' }));

    expect(screen.queryByRole('dialog')).toBeNull();
    const after = await loadConnections();
    expect(after.connections.map((connection) => [connection.url, connection.connectionId])).toEqual([
      ['ws://100.1.2.3:49200', 'conn-1'], ['ws://203.0.113.9:49200', 'conn-2'],
    ]);
    expect(after.connections[0].token).toBe('kept');
  });
});
