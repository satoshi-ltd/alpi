import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  return { View, Text };
});

vi.mock('expo-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn() }),
}));
vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
}));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink2: '#333', success: '#0a0' },
    fonts: { sans: { regular: 'r', semibold: 's' } },
    fontSizes: { lg: 15, display: 28 },
    lineHeights: { relaxed: 1.6 },
  }),
}));
vi.mock('../src/components/Button', () => ({
  Button: ({ title }) => React.createElement('button', { type: 'button' }, title),
}));
vi.mock('../src/components/Icon', () => ({ Icon: () => null }));
vi.mock('../src/components/AlpiMark', () => ({ AlpiMark: () => null }));

import Onboarding from '../app/onboarding.jsx';
import PairSuccess from '../app/paired.jsx';

describe('pairing copy vocabulary', () => {
  it('keeps Alpi as the product name and profiles as the entity on onboarding', () => {
    const { container } = render(<Onboarding />);
    expect(screen.getByText('Connect to Alpi')).toBeTruthy();
    expect(screen.getByText(/talk to your profiles from anywhere/)).toBeTruthy();
    expect(container.textContent).not.toMatch(/alpis\b/i);
  });

  it('calls the entity a profile on the paired screen', () => {
    const { container } = render(<PairSuccess />);
    expect(screen.getByText('Your daemon is reachable and your profiles are available.')).toBeTruthy();
    expect(container.textContent).not.toMatch(/alpis\b/i);
  });
});
