import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const starts = vi.hoisted(() => []);
const h = vi.hoisted(() => ({ announced: [], loops: 0, reduce: false, close: null, sets: [] }));

vi.mock('react-native', () => {
  const View = ({ children, style, pointerEvents, ...p }) =>
    React.createElement('div', style?.shadowColor ? { 'data-shadow': style.shadowColor, 'data-radius': style.borderRadius } : {}, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', {}, children);
  const Modal = ({ children, visible, supportedOrientations, onRequestClose }) => {
    h.close = onRequestClose;
    return visible
      ? React.createElement('div', { 'data-orientations': (supportedOrientations ?? []).join(',') }, children)
      : null;
  };
  const Animated = {
    Value: class {
      constructor(value) {
        this.value = value;
      }
      setValue(next) {
        h.sets.push(next);
        this.value = next;
      }
    },
    timing: () => ({ start: () => {} }),
    parallel: () => ({ start: (cb) => { starts.push(cb); } }),
    sequence: () => ({}),
    loop: () => { h.loops += 1; return { start: () => {}, stop: () => {} }; },
    View,
  };
  const Pressable = ({ children, onPress, accessibilityLabel }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel }, typeof children === 'function' ? children({ pressed: false }) : children);
  return { Animated, AccessibilityInfo: { announceForAccessibility: (text) => h.announced.push(text) }, Easing: { inOut: (fn) => fn, ease: 'ease' }, Modal, Pressable, Text, View };
});

vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));
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

describe('Toast replaced while hiding', () => {
  it('keeps the new toast when the old one is still sliding away', () => {
    vi.useFakeTimers();
    let toast;
    function Grab() {
      toast = useToast();
      return null;
    }
    render(<ToastProvider><Grab /></ToastProvider>);
    act(() => toast({ title: 'Deleted first', duration: 1000 }));
    act(() => { vi.advanceTimersByTime(1100); });
    const hiding = starts.at(-1);
    act(() => toast({ title: 'Deleted second' }));
    act(() => hiding({ finished: false }));
    expect(screen.getByText('Deleted second')).toBeTruthy();
    vi.useRealTimers();
  });
});

describe('Toast accessibility', () => {
  function Say({ toast: payload }) {
    const toast = useToast();
    React.useEffect(() => { toast(payload); }, [toast, payload]);
    return null;
  }
  const once = (payload) => render(<ToastProvider><Say toast={payload} /></ToastProvider>);

  it('says what it shows to a screen reader', () => {
    h.announced.length = 0;
    once({ title: 'Run failed', message: 'timed out', kind: 'danger' });
    expect(h.announced).toEqual(['Run failed. timed out']);
  });

  it('lets the hardware Back button dismiss the toast instead of swallowing it', () => {
    once({ message: 'Saved', kind: 'success' });
    expect(screen.getByText('Saved')).toBeTruthy();
    starts.length = 0;
    act(() => { h.close(); });
    act(() => { starts.pop()({ finished: true }); });
    expect(screen.queryByText('Saved')).toBeNull();
  });
});

describe('Toast identity', () => {
  it('hands out the same show function when the reduce-motion setting flips', () => {
    const seen = [];
    function Capture() {
      seen.push(useToast());
      return null;
    }
    const tree = () => <ToastProvider><Capture /></ToastProvider>;
    const view = render(tree());
    h.reduce = true;
    try {
      view.rerender(tree());
    } finally {
      h.reduce = false;
    }
    expect(seen.length).toBeGreaterThan(1);
    expect(new Set(seen).size).toBe(1);
  });
});

describe('Toast with reduced motion', () => {
  it('appears at once and never pulses its dot', () => {
    h.reduce = true;
    h.loops = 0;
    h.sets.length = 0;
    starts.length = 0;
    try {
      render(<ToastProvider><Trigger2 /></ToastProvider>);
      expect(h.loops).toBe(0);
      expect(h.sets).toEqual([0, 1]);
      expect(starts).toHaveLength(0);
    } finally {
      h.reduce = false;
    }
  });
});

function Trigger2() {
  const toast = useToast();
  React.useEffect(() => { toast({ message: 'Deleted', kind: 'danger' }); }, [toast]);
  return null;
}
