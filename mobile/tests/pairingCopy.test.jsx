import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => import('./mocks/firstRun.js'));
vi.mock('../src/theme/ThemeContext', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Button', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Fold', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Icon', () => import('./mocks/firstRun.js'));
vi.mock('../src/components/Toggle', () => import('./mocks/firstRun.js'));
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }) }));
vi.mock('../src/features/aln/notify', () => ({ getPermissionStatus: vi.fn(async () => 'undetermined'), requestPermission: vi.fn(async () => 'granted') }));
vi.mock('../src/lib/biometric', () => ({
  biometricCapabilities: vi.fn(async () => ({ hasHardware: false, enrolled: false, label: 'Biometric' })),
  getBiometricPref: vi.fn(async () => false),
  setBiometricPref: vi.fn(async () => {}),
  authenticate: vi.fn(async () => true),
}));

const nav = vi.hoisted(() => ({ calls: [], params: {} }));
vi.mock('expo-router', () => ({
  useLocalSearchParams: () => nav.params,
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
    replace: (to) => nav.calls.push(['replace', to]),
    canDismiss: () => true,
    dismissAll: () => nav.calls.push(['dismissAll']),
  }),
}));

import Onboarding from '../app/onboarding.jsx';
import PairSuccess from '../app/paired.jsx';

describe('pairing copy vocabulary', () => {
  it('keeps Alpi as the product name and profiles as the entity on onboarding', () => {
    const { container } = render(<Onboarding />);
    expect(screen.getByText('Pair with your alpi')).toBeTruthy();
    expect(screen.getByText(/its profiles come with you/)).toBeTruthy();
    expect(container.textContent).not.toMatch(/alpis\b/i);
  });

  it('greets with the alpaca fold in the theme ink', () => {
    const { container } = render(<Onboarding />);
    const mark = container.querySelector('[data-fold]');
    expect(mark.getAttribute('data-fold')).toBe('alpaca');
    expect(mark.getAttribute('data-size')).toBe('72');
  });

  it('calls the entity a profile on the paired screen', () => {
    const { container } = render(<PairSuccess />);
    expect(screen.getByText('Your daemon is reachable and your profiles are available.')).toBeTruthy();
    expect(container.textContent).not.toMatch(/alpis\b/i);
  });
});

describe('leaving onboarding', () => {
  it('clears the onboarding screens before opening the inbox, so Back never returns to them', () => {
    nav.calls.length = 0;
    render(<PairSuccess />);
    fireEvent.click(screen.getByText('Open inbox'));
    expect(nav.calls).toEqual([['dismissAll'], ['replace', '/']]);
  });
});

