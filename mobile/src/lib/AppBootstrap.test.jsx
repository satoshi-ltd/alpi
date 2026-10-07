import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ endpointReady: false, bioOn: false, unlock: false }));

vi.mock('react-native', () => ({
  View: ({ children }) => React.createElement('div', {}, children),
  Text: ({ children }) => React.createElement('span', {}, children),
  Pressable: ({ children, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, children),
}));
vi.mock('expo-router', () => ({ useRouter: () => ({ replace: vi.fn() }), useSegments: () => ['index'] }));
vi.mock('../components/Fold', () => ({
  Fold: ({ fold, color, size }) => React.createElement('span', { 'data-fold': fold, 'data-color': color ?? '', 'data-size': size }),
}));
vi.mock('../components/Busy', () => ({
  Busy: ({ label, size }) => React.createElement('span', { 'data-busy': size }, label),
}));
vi.mock('../features/aln/backgroundTask', () => ({ ensureRegistered: async () => {} }));
vi.mock('./biometric', () => ({
  getBiometricPref: async () => h.bioOn,
  biometricCapabilities: async () => ({ hasHardware: true, enrolled: true, label: 'Face ID' }),
  authenticate: async () => h.unlock,
}));
vi.mock('./EndpointContext', () => ({ useEndpoint: () => ({ ready: h.endpointReady, connections: [{ id: 'c1' }] }) }));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', bgPane: '#fff', ink: '#000', ink2: '#333', ink3: '#666' },
    fonts: { mono: 'mono', sans: { regular: 'r', medium: 'm', semibold: 's' } },
    fontSizes: { xs: 11, md: 14, xxl: 28 },
  }),
}));

import { AppBootstrap } from './AppBootstrap';

beforeEach(() => {
  h.endpointReady = false;
  h.bioOn = false;
  h.unlock = false;
});

const markOf = (container) => container.querySelector('[data-fold]');

describe('AppBootstrap brand mark', () => {
  it('waits with the ink alpaca and its words while connecting, never a still mark beside a spinner', async () => {
    const { container, getByText } = render(<AppBootstrap><span>app</span></AppBootstrap>);
    await act(async () => {});
    expect(getByText('Connecting').getAttribute('data-busy')).toBe('64');
    expect(markOf(container)).toBeNull();
  });

  it('draws the alpaca fold on the biometric lock screen', async () => {
    h.endpointReady = true;
    h.bioOn = true;
    const { container, getByText } = render(<AppBootstrap><span>app</span></AppBootstrap>);
    await act(async () => {});
    expect(getByText('Locked')).toBeTruthy();
    expect(markOf(container).getAttribute('data-fold')).toBe('alpaca');
    expect(markOf(container).getAttribute('data-size')).toBe('72');
  });
});
