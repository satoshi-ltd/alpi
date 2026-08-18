import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, pointerEvents, ...p }) => React.createElement('div', {}, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', {}, children);
  const Modal = ({ children, visible, supportedOrientations }) =>
    visible
      ? React.createElement('div', { 'data-orientations': (supportedOrientations ?? []).join(',') }, children)
      : null;
  const Animated = {
    Value: class {
      constructor(value) {
        this.value = value;
      }
    },
    timing: () => ({ start: () => {} }),
    parallel: () => ({ start: () => {} }),
    sequence: () => ({}),
    loop: () => ({ start: () => {}, stop: () => {} }),
    View,
  };
  return { Animated, Easing: { inOut: (fn) => fn, ease: 'ease' }, Modal, Text, View };
});

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
}));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bgPane: '#fff', ink: '#000', ink2: '#333', ink3: '#666', success: '#0a0', warning: '#fa0', danger: '#f00' },
    fonts: { sans: { regular: 'Inter_400Regular', semibold: 'Inter_600SemiBold' } },
    fontSizes: { md: 14 },
  }),
}));

import { ToastProvider, useToast } from './Toast';

function Trigger() {
  const toast = useToast();
  React.useEffect(() => {
    toast({ title: 'Profile saved' });
  }, [toast]);
  return null;
}

describe('Toast rotation', () => {
  it('lets the device rotate while a toast is up', () => {
    const { container } = render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    expect(container.querySelector('[data-orientations]').getAttribute('data-orientations')).toBe(
      'portrait,landscape-left,landscape-right',
    );
  });
});
