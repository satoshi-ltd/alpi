import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, pointerEvents, ...p }) =>
    React.createElement('div', style?.shadowColor ? { 'data-shadow': style.shadowColor, 'data-radius': style.borderRadius } : {}, children);
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
  const Pressable = ({ children, onPress, accessibilityLabel }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel }, typeof children === 'function' ? children({ pressed: false }) : children);
  return { Animated, Easing: { inOut: (fn) => fn, ease: 'ease' }, Modal, Pressable, Text, View };
});

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
}));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { selected: '#ddd', bgPane: '#fff', ink: '#000', ink2: '#333', ink3: '#666', success: '#0a0', warning: '#fa0', danger: '#f00' },
    fonts: { sans: { regular: 'Geist_400Regular', semibold: 'Geist_600SemiBold' } },
    fontSizes: { md: 14 },
    shadow: { base: { shadowColor: '#token-shadow', shadowRadius: 24 } },
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

describe('Toast elevation', () => {
  it('casts the theme shadow, not a literal one', () => {
    const { container } = render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    expect(container.querySelector('[data-shadow]').getAttribute('data-shadow')).toBe('#token-shadow');
  });

  it('cuts the toast as a 4 pt card', () => {
    const { container } = render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    expect(container.querySelector('[data-shadow]').getAttribute('data-radius')).toBe('4');
  });
});

describe('Toast action', () => {
  function Undoable({ onAction }) {
    const toast = useToast();
    React.useEffect(() => {
      toast({ message: 'Deleted', action: 'Undo', onAction, duration: 5000 });
    }, [toast, onAction]);
    return null;
  }

  it('offers the action as a button that runs once and dismisses the toast', () => {
    const onAction = vi.fn();
    render(
      <ToastProvider>
        <Undoable onAction={onAction} />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByLabelText('Undo'));
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it('draws no button for a plain toast', () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    expect(screen.queryByRole('button')).toBeNull();
  });
});
