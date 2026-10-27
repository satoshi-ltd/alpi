import React from 'react';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { Keyboard, emit, reset, state } from './mocks/firstRun.js';

afterEach(cleanup);

const h = vi.hoisted(() => ({ connections: [], replace: vi.fn(), call: vi.fn(), probe: vi.fn(), clip: vi.fn(async () => '') }));

vi.mock('react-native', () => import('./mocks/firstRun.js'));
vi.mock('../src/theme/ThemeContext', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Button', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Fold', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Busy', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Icon', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/KeyboardPane', () => import('./mocks/firstRun.js'));
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }) }));
vi.mock('expo-camera', () => ({ CameraView: () => null, useCameraPermissions: () => [{ granted: true }, vi.fn(), vi.fn()] }));
vi.mock('expo-clipboard', () => ({ getStringAsync: (...args) => h.clip(...args) }));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.3.1' } } }));
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: h.replace, canGoBack: () => true }),
  usePathname: () => '/pair',
  useLocalSearchParams: () => ({}),
}));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ addConnection: vi.fn(), connections: h.connections }) }));
vi.mock('../src/lib/rpc', async () => {
  const actual = await vi.importActual('../src/lib/rpc');
  return { ...actual, call: (...args) => h.call(...args) };
});
vi.mock('../src/lib/probe', () => ({ probe: (...args) => h.probe(...args) }));

import Pair from '../app/pair.jsx';

const style = (el) => JSON.parse(el.getAttribute('data-style') ?? '{}');
const primaries = () => [...document.querySelectorAll('button[data-variant="primary"]')];
const input = () => document.querySelector('[data-pair-input]');
const LINK = 'alpi://device?url=ws%3A%2F%2F100.1.2.3%3A49200&name=casa&pairing_token=abc';

beforeEach(() => {
  reset();
  h.connections = [];
  h.replace.mockReset();
  h.call.mockReset();
  h.probe.mockReset();
  h.clip.mockReset();
  h.clip.mockResolvedValue('');
});

describe('paste state', () => {
  it('has one primary, Pair, disabled until a link is in, over the ghost Scan QR', () => {
    render(<Pair />);
    expect(primaries().map((b) => b.textContent)).toEqual(['Pair']);
    const pair = screen.getByText('Pair');
    expect([pair.dataset.size, pair.dataset.height, pair.disabled]).toEqual(['hero', '56', true]);
    const scan = screen.getByText('Scan QR');
    expect([scan.dataset.variant, scan.dataset.size, scan.dataset.height]).toEqual(['ghost', 'lg', '48']);
    fireEvent.change(input(), { target: { value: LINK } });
    expect(screen.getByText('Pair').disabled).toBe(false);
    expect(primaries()).toHaveLength(1);
  });

  it('draws the title, the link label and the field on the edge with no arrow and no card', () => {
    const { container } = render(<Pair />);
    expect(screen.getByText('Pair this phone')).toBeTruthy();
    expect(screen.getByText('alpi:// link')).toBeTruthy();
    expect(container.querySelector('[data-icon]')).toBeNull();
    expect(container.querySelector('[aria-label="Back"]')).toBeNull();
    expect(screen.queryByText('Connect to your daemon')).toBeNull();
    expect(screen.queryByText('or paste link')).toBeNull();
    expect(container.innerHTML).not.toContain('"backgroundColor":"#f4f4f4"');
  });

  it('keeps the shipped title in the theme semibold font and the mark at 72 pt on the edge', () => {
    const { container } = render(<Pair />);
    expect(style(screen.getByText('Pair this phone')).fontFamily).toMatch(/600SemiBold/);
    const mark = container.querySelector('[data-fold]');
    expect(mark.dataset.size).toBe('72');
    expect(style(mark.parentElement).marginLeft).toBeCloseTo(-12.42, 2);
  });

  it('makes Paste from clipboard a 44 pt ghost whose text starts on the edge', async () => {
    h.clip.mockResolvedValue(LINK);
    render(<Pair />);
    const paste = screen.getByText('Paste from clipboard');
    expect([paste.dataset.variant, paste.dataset.size, paste.dataset.height]).toEqual(['ghost', 'md', '44']);
    expect(style(paste.parentElement).marginLeft).toBe(-14);
    fireEvent.click(paste);
    await waitFor(() => expect(input().value).toBe(LINK));
    expect(screen.getByText('casa · ws://100.1.2.3:49200')).toBeTruthy();
  });

  it('lists the sources as mono paths under their labels', () => {
    render(<Pair />);
    expect(screen.getByText('In the alpi desktop app')).toBeTruthy();
    expect(style(screen.getByText('Settings → Connections → New connection')).fontFamily).toMatch(/Mono/);
  });

  it('opens the scanner from the ghost', () => {
    const { container } = render(<Pair />);
    fireEvent.click(screen.getByText('Scan QR'));
    expect(screen.getByText('Scan the QR shown on your daemon')).toBeTruthy();
    expect(container.querySelector('[data-icon]')).toBeNull();
  });
});

describe('keyboard open', () => {
  it('hides the mark and the sources so the field is the first control, and drops the safe-area pad', () => {
    const { container } = render(<Pair />);
    act(() => emit('keyboardWillShow'));
    expect(container.querySelector('[data-fold]')).toBeNull();
    expect(screen.queryByText('In the alpi desktop app')).toBeNull();
    const title = screen.getByText('Pair this phone');
    expect(style(title).marginTop).toBe(0);
    const bar = screen.getByText('Pair').parentElement.parentElement;
    expect(style(bar).paddingBottom).toBe(16);
    expect(document.querySelector('[data-keyboard-pane]').contains(bar)).toBe(true);
    act(() => emit('keyboardWillHide'));
    expect(container.querySelector('[data-fold]')).toBeTruthy();
    expect(style(screen.getByText('Pair').parentElement.parentElement).paddingBottom).toBe(50);
  });
});

describe('connecting', () => {
  const connect = async () => {
    h.call.mockReturnValue(new Promise(() => {}));
    render(<Pair />);
    fireEvent.change(input(), { target: { value: LINK } });
    fireEvent.click(screen.getByText('Pair'));
    await waitFor(() => expect(document.querySelector('[data-busy]')).toBeTruthy());
  };

  it('shows Busy at 77 pt in the Fold place, the ladder, and no button at all', async () => {
    await connect();
    const busy = document.querySelector('[data-busy]');
    expect(busy.dataset.size).toBe('77');
    expect(style(busy).marginLeft).toBeCloseTo(-13.29, 2);
    expect(document.querySelector('[data-fold]')).toBeNull();
    expect(screen.getByText('Reaching casa').closest('[data-state]').dataset.state).toBe('now');
    expect(screen.queryByText('Pair')).toBeNull();
    expect(screen.queryByText('Pairing…')).toBeNull();
    expect(screen.queryByText('Scan QR')).toBeNull();
    expect(screen.queryByText('Paste from clipboard')).toBeNull();
    expect(screen.queryByText('In the alpi desktop app')).toBeNull();
  });

  it('has exactly one wait indicator: no button spinner beside the ladder', async () => {
    await connect();
    expect(document.querySelectorAll('[role="progressbar"]')).toHaveLength(1);
    expect(document.querySelectorAll('button[data-loading="true"]')).toHaveLength(0);
    expect(input().disabled).toBe(true);
  });

  it('keeps the title where it was while the page changes state', async () => {
    const { container } = render(<Pair />);
    const before = style(screen.getByText('Pair this phone'));
    h.call.mockReturnValue(new Promise(() => {}));
    fireEvent.change(input(), { target: { value: LINK } });
    fireEvent.click(screen.getByText('Pair'));
    await waitFor(() => expect(container.querySelector('[data-busy]')).toBeTruthy());
    expect(style(screen.getByText('Pair this phone'))).toEqual(before);
  });
});

describe('failed', () => {
  it('shows the Fold again, the host fact, the failure between the ladder and the buttons, and keeps the link', async () => {
    h.call.mockRejectedValue(Object.assign(new Error('connection failed'), { transport: true }));
    const { container } = render(<Pair />);
    fireEvent.change(input(), { target: { value: LINK } });
    fireEvent.click(screen.getByText('Pair'));
    await waitFor(() => expect(screen.getByText("Can't reach casa")).toBeTruthy());
    expect(container.querySelector('[data-fold]')).toBeTruthy();
    expect(container.querySelector('[data-busy]')).toBeNull();
    expect(screen.getByText('casa · ws://100.1.2.3:49200')).toBeTruthy();
    const ladder = screen.getByText('Link read').closest('[role="list"]');
    const failure = screen.getByText("Can't reach casa").parentElement;
    const actions = screen.getByText('Try again').parentElement;
    expect(ladder.compareDocumentPosition(failure) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(failure.compareDocumentPosition(actions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText('Check that the host is on and reachable from here, then try again.')).toBeTruthy();
    expect(document.querySelectorAll('[role="progressbar"]')).toHaveLength(0);
  });
});

describe('leaving /pair', () => {
  const saved = [{ id: 'c1', name: 'casa' }];

  it('keeps Scan QR as the ghost when nothing is saved yet', () => {
    render(<Pair />);
    expect(screen.getByText('Scan QR')).toBeTruthy();
    expect(screen.queryByText('Open inbox')).toBeNull();
  });

  it('offers a ghost Open inbox after Scan QR when a connection is saved, under the one primary', () => {
    h.connections = saved;
    render(<Pair />);
    const open = screen.getByText('Open inbox');
    const scan = screen.getByText('Scan QR');
    expect([open.dataset.variant, open.dataset.size, open.dataset.height]).toEqual(['ghost', 'lg', '48']);
    expect([scan.dataset.variant, scan.dataset.height]).toEqual(['ghost', '48']);
    expect(scan.compareDocumentPosition(open) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText('Pair').compareDocumentPosition(scan) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(primaries().map((b) => b.textContent)).toEqual(['Pair']);
    fireEvent.click(scan);
    expect(screen.getByText('Scan the QR shown on your daemon')).toBeTruthy();
    cleanup();
    h.connections = saved;
    render(<Pair />);
    fireEvent.click(screen.getByText('Open inbox'));
    expect(h.replace).toHaveBeenCalledWith('/');
  });

  it('keeps both ghosts after a failure that leaves the link retryable', async () => {
    h.connections = saved;
    h.call.mockRejectedValue(Object.assign(new Error('connection failed'), { transport: true }));
    render(<Pair />);
    fireEvent.change(input(), { target: { value: LINK } });
    fireEvent.click(screen.getByText('Pair'));
    await waitFor(() => expect(screen.getByText("Can't reach casa")).toBeTruthy());
    expect(primaries().map((b) => b.textContent)).toEqual(['Try again']);
    expect(screen.getByText('Open inbox').dataset.variant).toBe('ghost');
    expect(screen.getByText('Scan QR').dataset.variant).toBe('ghost');
  });
});

describe('pairing guards', () => {
  it('dismisses the keyboard as pairing starts so the connecting state never waits on a hide event', async () => {
    h.call.mockReturnValue(new Promise(() => {}));
    render(<Pair />);
    fireEvent.change(input(), { target: { value: LINK } });
    fireEvent.click(screen.getByText('Pair'));
    expect(Keyboard.dismiss).toHaveBeenCalledTimes(1);
  });

  it('does not navigate to the paired screen after the page was left during connecting', async () => {
    let finish;
    h.call.mockImplementation((_e, method) => (method === 'host.connections.exchange_pairing'
      ? new Promise((resolve) => { finish = () => resolve({ token: 't' }); })
      : Promise.resolve({})));
    h.probe.mockResolvedValue({ status: 'online', deviceId: 'd1', deviceName: 'casa', role: 'admin' });
    const view = render(<Pair />);
    fireEvent.change(input(), { target: { value: LINK } });
    fireEvent.click(screen.getByText('Pair'));
    await waitFor(() => expect(finish).toBeTypeOf('function'));
    view.unmount();
    await act(async () => {
      finish();
      for (let i = 0; i < 10; i += 1) await Promise.resolve();
    });
    expect(h.probe).toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
  });
});
