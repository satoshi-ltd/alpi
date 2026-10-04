import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  return { View, Text };
});

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
  Button: ({ title, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, title),
}));
vi.mock('../src/components/Icon', () => ({ Icon: () => null }));
vi.mock('../src/components/Fold', () => ({
  Fold: ({ fold, color, size }) => React.createElement('span', { 'data-fold': fold, 'data-color': color ?? '', 'data-size': size }),
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
    expect(mark.getAttribute('data-color')).toBe('');
    expect(mark.getAttribute('data-size')).toBe('88');
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

