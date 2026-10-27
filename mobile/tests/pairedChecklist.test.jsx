import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { Linking, flip, reset, state } from './mocks/firstRun.js';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  params: { host: 'casa', role: 'admin' },
  caps: { hasHardware: true, enrolled: true, label: 'Face ID' },
  pref: false,
  perm: 'undetermined',
  flag: null,
  order: [],
  result: 'granted',
  throws: false,
  replace: vi.fn(),
  setPref: vi.fn(),
  auth: vi.fn(),
}));

vi.mock('react-native', () => import('./mocks/firstRun.js'));
vi.mock('../src/theme/ThemeContext', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Button', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Fold', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Icon', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Toggle', () => import('./mocks/firstRun.js'));
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }) }));
vi.mock('expo-router', () => ({
  useLocalSearchParams: () => h.params,
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: h.replace, canDismiss: () => true, dismissAll: vi.fn() }),
}));
vi.mock('../src/features/aln/notify', () => ({
  getPermissionStatus: vi.fn(() => Promise.resolve(h.perm)),
  requestPermission: vi.fn(async () => {
    h.order.push('request');
    if (h.throws) throw new Error('native');
    return h.result;
  }),
}));
vi.mock('../src/features/aln/state', () => ({
  PRIMER_FLAG: 'notificationPrimer',
  loadFlag: vi.fn(async () => h.flag),
  saveFlag: vi.fn(async (name, value) => {
    h.flag = value;
    h.order.push(`flag:${value}`);
  }),
}));
vi.mock('../src/lib/biometric', () => ({
  biometricCapabilities: vi.fn(async () => h.caps),
  getBiometricPref: vi.fn(async () => h.pref),
  setBiometricPref: (...args) => h.setPref(...args),
  authenticate: (...args) => h.auth(...args),
}));

import PairSuccess from '../app/paired.jsx';
import { saveFlag } from '../src/features/aln/state';

const style = (el) => JSON.parse(el.getAttribute('data-style') ?? '{}');
const primaries = () => [...document.querySelectorAll('button[data-variant="primary"]')];
const ready = () => waitFor(() => expect(screen.getByText('Enable')).toBeTruthy());

beforeEach(() => {
  reset();
  h.params = { host: 'casa', role: 'admin' };
  h.caps = { hasHardware: true, enrolled: true, label: 'Face ID' };
  h.pref = false;
  h.perm = 'undetermined';
  h.flag = null;
  h.order = [];
  h.result = 'granted';
  h.throws = false;
  h.replace.mockReset();
  h.setPref.mockReset();
  h.auth.mockReset();
  h.auth.mockResolvedValue(true);
  vi.mocked(saveFlag).mockClear();
});

describe('paired checklist', () => {
  it('lists the facts on the edge and two optional rows, no card', async () => {
    const { container } = render(<PairSuccess />);
    await ready();
    expect(screen.getByText('Paired with casa')).toBeTruthy();
    expect(screen.getByText('admin · all profiles')).toBeTruthy();
    expect(screen.getByText('Your daemon is reachable and your profiles are available.')).toBeTruthy();
    expect(screen.getByText('Optional')).toBeTruthy();
    expect(screen.getByText('Face ID unlock')).toBeTruthy();
    expect(screen.getByText('required on cold start')).toBeTruthy();
    expect(screen.getByText('Notifications')).toBeTruthy();
    expect(screen.getByText('built on this phone from your daemon · no push service')).toBeTruthy();
    const rows = screen.getByText('Notifications').closest('[role="list"]');
    expect(style(rows).marginHorizontal).toBe(-16);
    expect(container.querySelector('[data-fold]').dataset.size).toBe('72');
    expect(container.innerHTML).not.toContain('"backgroundColor":"#f4f4f4"');
  });

  it('has one primary, Open inbox at 56 pt, and the Enable control is a secondary of 44 pt', async () => {
    render(<PairSuccess />);
    await ready();
    expect(primaries().map((b) => b.textContent)).toEqual(['Open inbox']);
    const open = screen.getByText('Open inbox');
    expect([open.dataset.size, open.dataset.height, open.dataset.full]).toEqual(['hero', '56', 'true']);
    const enable = screen.getByText('Enable');
    expect([enable.dataset.variant, enable.dataset.size, enable.dataset.height]).toEqual(['secondary', 'md', '44']);
    const toggle = screen.getByRole('switch');
    expect(style(toggle.parentElement)).toMatchObject({ minHeight: 44, minWidth: 44 });
  });

  it('anchors Open inbox below the page, 16 pt above the safe area', async () => {
    render(<PairSuccess />);
    await ready();
    const scroll = document.querySelector('[data-scroll]');
    const bar = screen.getByText('Open inbox').parentElement.parentElement;
    expect(scroll.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(style(bar)).toEqual({ paddingHorizontal: 16, paddingTop: 16, paddingBottom: 50 });
  });

  it('never blocks Open inbox: enabled before the rows load and while a step is out', async () => {
    h.auth.mockReturnValue(new Promise(() => {}));
    render(<PairSuccess />);
    expect(screen.getByText('Open inbox').disabled).toBe(false);
    await ready();
    fireEvent.click(screen.getByRole('switch'));
    expect(screen.getByText('Open inbox').disabled).toBe(false);
    fireEvent.click(screen.getByText('Open inbox'));
    expect(h.replace).toHaveBeenCalledWith('/');
  });

  it('turns Face ID on through the device prompt and keeps the switch off when it is refused', async () => {
    h.auth.mockResolvedValueOnce(false);
    render(<PairSuccess />);
    await ready();
    fireEvent.click(screen.getByRole('switch'));
    await waitFor(() => expect(h.auth).toHaveBeenCalledWith('Enable Face ID unlock'));
    expect(h.setPref).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('switch'));
    await waitFor(() => expect(h.setPref).toHaveBeenCalledWith(true));
    await waitFor(() => expect(screen.getByRole('switch').checked).toBe(true));
  });

  it('names the row after the device biometric and hides it with no hardware or no enrolment', async () => {
    h.caps = { hasHardware: true, enrolled: true, label: 'Biometric' };
    const { unmount } = render(<PairSuccess />);
    await waitFor(() => expect(screen.getByText('Biometric unlock')).toBeTruthy());
    unmount();
    h.caps = { hasHardware: true, enrolled: false, label: 'Face ID' };
    render(<PairSuccess />);
    await ready();
    expect(screen.queryByRole('switch')).toBeNull();
    expect(screen.queryByText('Face ID unlock')).toBeNull();
    cleanup();
    h.caps = { hasHardware: false, enrolled: false, label: 'Biometric' };
    render(<PairSuccess />);
    await ready();
    expect(screen.queryByRole('switch')).toBeNull();
  });
});

describe('alerts', () => {
  const settle = async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  };

  it('asks first and saves the primer flag only after a granted result, then swaps Enable for the on pill', async () => {
    render(<PairSuccess />);
    await ready();
    h.order = [];
    fireEvent.click(screen.getByText('Enable'));
    await waitFor(() => expect(screen.getByText('on')).toBeTruthy());
    expect(h.order).toEqual(['request', 'flag:accepted']);
    expect(screen.queryByText('Enable')).toBeNull();
    expect(screen.getByText('Open inbox').disabled).toBe(false);
  });

  it('records a refusal as declined and then offers Open settings', async () => {
    h.result = 'denied';
    render(<PairSuccess />);
    await ready();
    h.order = [];
    fireEvent.click(screen.getByText('Enable'));
    await waitFor(() => expect(screen.getByText('Open settings')).toBeTruthy());
    expect(h.order).toEqual(['request', 'flag:declined']);
  });

  it.each(['undetermined', 'throw'])('writes no flag when the system answers %s', async (outcome) => {
    if (outcome === 'throw') h.throws = true;
    else h.result = 'undetermined';
    render(<PairSuccess />);
    await ready();
    h.order = [];
    fireEvent.click(screen.getByText('Enable'));
    await settle();
    expect(h.order).toEqual(['request']);
    expect(saveFlag).not.toHaveBeenCalled();
    expect(screen.getByText('Enable')).toBeTruthy();
  });

  it('shows Open settings, not Enable, when alerts were denied before, and opens the system settings', async () => {
    h.perm = 'denied';
    render(<PairSuccess />);
    await waitFor(() => expect(screen.getByText('Open settings')).toBeTruthy());
    expect(screen.queryByText('Enable')).toBeNull();
    const open = screen.getByText('Open settings');
    expect([open.dataset.variant, open.dataset.size, open.dataset.height]).toEqual(['secondary', 'md', '44']);
    fireEvent.click(open);
    expect(Linking.openSettings).toHaveBeenCalledTimes(1);
    expect(primaries().map((b) => b.textContent)).toEqual(['Open inbox']);
  });

  it('re-reads the permission when the app returns active, shows the on pill and records accepted once', async () => {
    h.perm = 'denied';
    render(<PairSuccess />);
    await waitFor(() => expect(screen.getByText('Open settings')).toBeTruthy());
    h.flag = 'declined';
    h.perm = 'granted';
    await act(async () => {
      flip('active');
      await settle();
    });
    expect(screen.getByText('on')).toBeTruthy();
    expect(screen.queryByText('Open settings')).toBeNull();
    await act(async () => {
      flip('active');
      await settle();
    });
    expect(vi.mocked(saveFlag).mock.calls.filter(([, v]) => v === 'accepted')).toHaveLength(1);
  });

  it('ignores backgrounding and removes its listener on unmount', async () => {
    h.perm = 'denied';
    const view = render(<PairSuccess />);
    await waitFor(() => expect(screen.getByText('Open settings')).toBeTruthy());
    h.perm = 'granted';
    await act(async () => {
      flip('background');
      await settle();
    });
    expect(screen.getByText('Open settings')).toBeTruthy();
    view.unmount();
    expect(state.appState).toHaveLength(0);
  });

  it('renders no control while the permission is still loading', async () => {
    h.perm = new Promise(() => {});
    render(<PairSuccess />);
    await waitFor(() => expect(screen.getByRole('switch')).toBeTruthy());
    expect(screen.queryByText('Enable')).toBeNull();
    expect(screen.queryByText('Open settings')).toBeNull();
    expect(screen.queryByText('on')).toBeNull();
    expect(screen.getByText('Open inbox').disabled).toBe(false);
  });

  it('shows the on pill at once when alerts were already granted', async () => {
    h.perm = 'granted';
    render(<PairSuccess />);
    await waitFor(() => expect(screen.getByText('on')).toBeTruthy());
    expect(screen.queryByText('Enable')).toBeNull();
  });

  it('never writes the primer flag on its own: leaving through Open inbox keeps the primer eligible', async () => {
    render(<PairSuccess />);
    await ready();
    fireEvent.click(screen.getByText('Open inbox'));
    await settle();
    expect(saveFlag).not.toHaveBeenCalled();
    expect(h.replace).toHaveBeenCalledWith('/');
  });
});

describe('paired on a fold', () => {
  it('is one full-bleed column on the 24 pt edge', async () => {
    state.width = 852;
    state.height = 884;
    render(<PairSuccess />);
    await ready();
    expect(JSON.parse(document.querySelector('[data-scroll]').getAttribute('data-content')).paddingHorizontal).toBe(24);
    expect(style(screen.getByText('Open inbox').parentElement.parentElement).paddingHorizontal).toBe(24);
    expect(style(screen.getByText('Paired with casa').parentElement).maxWidth).toBe(480);
  });
});
