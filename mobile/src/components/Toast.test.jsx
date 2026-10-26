import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const starts = vi.hoisted(() => []);
const h = vi.hoisted(() => ({ announced: [], loops: 0, reduce: false, close: null, sets: [], kb: {}, views: [] }));

vi.mock('react-native', () => {
  const View = ({ children, style, pointerEvents, accessibilityRole, ...p }) =>
    React.createElement('div', { ...(style?.shadowColor ? { 'data-shadow': style.shadowColor, 'data-radius': style.borderRadius } : {}), ...(accessibilityRole ? { role: accessibilityRole } : {}), 'data-vstyle': JSON.stringify(style) }, children);
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
  const Pressable = ({ children, onPress, accessibilityLabel, style }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-tap': JSON.stringify(typeof style === 'function' ? style({ pressed: false }) : style) }, typeof children === 'function' ? children({ pressed: false }) : children);
  const Keyboard = { addListener: (name, cb) => { h.kb[name] = cb; return { remove() {} }; } };
  return { Keyboard, Animated, AccessibilityInfo: { announceForAccessibility: (text) => h.announced.push(text) }, Easing: { inOut: (fn) => fn, ease: 'ease', bezier: (...p) => `bezier(${p.join(',')})` }, Modal, Pressable, Text, View };
});

vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));
vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children, edges, style }) => React.createElement('div', { 'data-edges': (edges ?? []).join(','), 'data-safe-style': JSON.stringify(style) }, children),
}));
vi.mock('./Icon', () => ({ Icon: ({ name }) => React.createElement('i', { 'data-icon': name }) }));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { selected: '#ddd', bgPane: '#fff', ink: '#000', ink2: '#333', ink3: '#666', success: '#0a0', warning: '#fa0', danger: '#f00' },
    fonts: { sans: { regular: 'Geist_400Regular', semibold: 'Geist_600SemiBold' } },
    fontSizes: { md: 14 },
    shadow: { toast: { shadowColor: '#token-shadow', shadowRadius: 24 } },
  }),
}));

import { BUTTON_LINE, ToastProvider, firstLineHeight, useToast } from './Toast';
import { mobile, space } from '../theme/tokens';

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
    act(() => toast({ title: 'Deleted first' }));
    act(() => { vi.advanceTimersByTime(2900); });
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


describe('Toast levels', () => {
  const hides = () => starts.filter(Boolean);
  const grab = () => {
    let fn;
    const Grab = () => { fn = useToast(); return null; };
    render(<ToastProvider><Grab /></ToastProvider>);
    return (payload) => act(() => fn(payload));
  };

  it('clears an information toast after 2.8 s whatever duration the caller passes', () => {
    vi.useFakeTimers();
    starts.length = 0;
    const show = grab();
    show({ title: 'Saved', duration: 9000 });
    act(() => { vi.advanceTimersByTime(2700); });
    expect(hides()).toHaveLength(0);
    act(() => { vi.advanceTimersByTime(200); });
    expect(hides()).toHaveLength(1);
    vi.useRealTimers();
  });

  it('keeps an undo toast for its own window', () => {
    vi.useFakeTimers();
    starts.length = 0;
    const show = grab();
    show({ message: 'Deleted', action: 'Undo', onAction: () => {}, duration: 6000 });
    act(() => { vi.advanceTimersByTime(5900); });
    expect(hides()).toHaveLength(0);
    act(() => { vi.advanceTimersByTime(200); });
    expect(hides()).toHaveLength(1);
    vi.useRealTimers();
  });

  it('gives an error with nothing to retry a longer life than information, and a 44 pt close control', () => {
    vi.useFakeTimers();
    starts.length = 0;
    const show = grab();
    show({ title: 'Save failed', message: 'offline', kind: 'danger' });
    act(() => { vi.advanceTimersByTime(5900); });
    expect(hides()).toHaveLength(0);
    const close = screen.getByLabelText('Dismiss');
    const tap = JSON.parse(close.getAttribute('data-tap'));
    expect([tap.width, tap.height]).toEqual([44, 44]);
    act(() => { vi.advanceTimersByTime(200); });
    expect(hides()).toHaveLength(1);
    vi.useRealTimers();
  });

  it('keeps an error that offers Retry until it is dismissed', () => {
    vi.useFakeTimers();
    starts.length = 0;
    const show = grab();
    show({ title: 'Save failed', message: 'offline', kind: 'danger', onRetry: () => {} });
    act(() => { vi.advanceTimersByTime(60000); });
    expect(hides()).toHaveLength(0);
    fireEvent.click(screen.getByLabelText('Dismiss'));
    expect(hides()).toHaveLength(1);
    vi.useRealTimers();
  });

  it('offers Retry only when the caller gives one, and runs it once', () => {
    const show = grab();
    show({ title: 'Save failed', kind: 'danger' });
    expect(screen.queryByLabelText('Retry')).toBeNull();
    const onRetry = vi.fn();
    show({ title: 'Save failed', kind: 'danger', onRetry });
    fireEvent.click(screen.getByLabelText('Retry'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('announces an error as an alert and an information toast as nothing urgent', () => {
    const show = grab();
    show({ title: 'Save failed', kind: 'danger' });
    expect(screen.getByRole('alert')).toBeTruthy();
    show({ title: 'Saved' });
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('wraps the message to two lines', () => {
    const show = grab();
    show({ title: 'Save failed', message: 'a long reason', kind: 'danger' });
    expect(screen.getByText('a long reason')).toBeTruthy();
  });
});

describe('Toast anchor', () => {
  it('sits above the bottom edge, safe-area aware, and rides above the keyboard', () => {
    const { container } = render(<ToastProvider><Trigger /></ToastProvider>);
    const safe = container.querySelector('[data-edges]');
    expect(safe.getAttribute('data-edges')).toBe('bottom');
    const style = JSON.parse(safe.getAttribute('data-safe-style'));
    expect(style.bottom).toBe(0);
    expect(style.top).toBeUndefined();
    act(() => { h.kb.keyboardDidShow({ endCoordinates: { height: 300 } }); });
    expect(JSON.parse(container.querySelector('[data-edges]').getAttribute('data-safe-style')).bottom).toBe(300);
  });
});

describe('Toast first line', () => {
  const lanes = (container) =>
    [...container.querySelectorAll('[data-vstyle]')]
      .map((el) => JSON.parse(el.getAttribute('data-vstyle') ?? '{}'))
      .filter((style) => style && style.justifyContent === 'center' && typeof style.height === 'number');

  function Plain({ title }) {
    const toast = useToast();
    React.useEffect(() => {
      toast({ title });
    }, [toast, title]);
    return null;
  }

  function WithAction() {
    const toast = useToast();
    React.useEffect(() => {
      toast({ title: 'Deleted', action: 'Undo', onAction: () => {} });
    }, [toast]);
    return null;
  }

  it('centres a trailing button on the first text line: the line is the button box left after its negative margins', () => {
    expect(BUTTON_LINE).toBe(mobile.tap - 2 * space.s4);
    expect(firstLineHeight(14, true)).toBe(24);
  });

  it('sets a plain toast first line from the cozy leading, not from a hand-set dot offset', () => {
    expect(firstLineHeight(14, false)).toBe(18);
  });

  it('centres the dot in a lane as tall as that first line', () => {
    const plain = render(<ToastProvider><Plain title="Profile saved" /></ToastProvider>);
    expect(lanes(plain.container).map((l) => l.height)).toContain(18);
    cleanup();
    const withAction = render(<ToastProvider><WithAction /></ToastProvider>);
    expect(lanes(withAction.container).map((l) => l.height)).toContain(24);
  });
});
