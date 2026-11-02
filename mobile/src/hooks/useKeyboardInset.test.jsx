import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({ listeners: {}, visible: false, metrics: undefined, platform: { OS: 'android' } }));

vi.mock('react-native', () => {
  const on = (event, fn) => {
    h.listeners[event] = fn;
    return { remove: () => { delete h.listeners[event]; } };
  };
  return {
    Keyboard: { addListener: on, isVisible: () => h.visible, metrics: () => h.metrics },
    AppState: { addEventListener: (_e, fn) => on('appstate', fn) },
    Dimensions: { addEventListener: (_e, fn) => on('dimensions', fn) },
    Platform: h.platform,
  };
});
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 0, bottom: 34, left: 0, right: 0 }) }));

import { KeyboardState, state as keyboard } from '../../tests/mocks/reanimated.js';
import { keyboardInset, useKeyboardInset } from './useKeyboardInset';

beforeEach(() => {
  h.listeners = {};
  h.visible = false;
  h.metrics = undefined;
  h.platform.OS = 'android';
  keyboard.keyboardHeight = 0;
  keyboard.keyboardState = KeyboardState.UNKNOWN;
});

const emit = (event, payload) => act(() => h.listeners[event](payload));

describe('keyboardInset', () => {
  it('follows the animation while the keyboard moves, even after a hide event', () => {
    expect(keyboardInset({ height: 120, state: KeyboardState.CLOSING, closed: true, fallback: 0 })).toBe(120);
    expect(keyboardInset({ height: 80, state: KeyboardState.OPENING, closed: true, fallback: 0 })).toBe(80);
  });

  it('drops a height left behind by a keyboard that closed without animating', () => {
    expect(keyboardInset({ height: 300, state: KeyboardState.OPEN, closed: true, fallback: 0 })).toBe(0);
  });

  it('uses the reported keyboard when one opened without animating', () => {
    expect(keyboardInset({ height: 0, state: KeyboardState.CLOSED, closed: false, fallback: 314 })).toBe(314);
    expect(keyboardInset({ height: 300, state: KeyboardState.OPEN, closed: false, fallback: 314 })).toBe(300);
  });
});

describe('useKeyboardInset', () => {
  it('drops to zero when the keyboard hides without an animation, e.g. on a fold', () => {
    h.visible = true;
    keyboard.keyboardHeight = 300;
    keyboard.keyboardState = KeyboardState.OPEN;
    const { result, rerender } = renderHook(() => useKeyboardInset());
    expect(result.current.value).toBe(300);
    emit('keyboardDidHide');
    rerender();
    expect(result.current.value).toBe(0);
  });

  it('pads by the reported keyboard plus the nav bar when it opens without an animation', () => {
    keyboard.keyboardState = KeyboardState.CLOSED;
    const { result, rerender } = renderHook(() => useKeyboardInset());
    expect(result.current.value).toBe(0);
    emit('keyboardDidShow', { endCoordinates: { height: 280 } });
    rerender();
    expect(result.current.value).toBe(314);
  });

  it('settles a stale height on resume and on a display change', () => {
    h.visible = true;
    keyboard.keyboardHeight = 300;
    keyboard.keyboardState = KeyboardState.OPEN;
    const { result, rerender } = renderHook(() => useKeyboardInset());
    h.visible = false;
    emit('appstate', 'active');
    rerender();
    expect(result.current.value).toBe(0);
    keyboard.keyboardHeight = 0;
    keyboard.keyboardState = KeyboardState.CLOSED;
    h.visible = true;
    h.metrics = { height: 250 };
    emit('dimensions');
    rerender();
    expect(result.current.value).toBe(284);
  });

  it('starts closed when no keyboard is up, whatever height reanimated kept', () => {
    keyboard.keyboardHeight = 300;
    keyboard.keyboardState = KeyboardState.OPEN;
    const { result, rerender } = renderHook(() => useKeyboardInset());
    rerender();
    expect(result.current.value).toBe(0);
  });

  it('takes the reported iOS keyboard as is, since its frame already covers the home indicator', () => {
    h.platform.OS = 'ios';
    keyboard.keyboardState = KeyboardState.CLOSED;
    const { result, rerender } = renderHook(() => useKeyboardInset());
    emit('keyboardDidShow', { endCoordinates: { height: 336 } });
    rerender();
    expect(result.current.value).toBe(336);
  });

  it('keeps an opening keyboard when a resync lands before its show event', () => {
    keyboard.keyboardHeight = 120;
    keyboard.keyboardState = KeyboardState.OPENING;
    const { result, rerender } = renderHook(() => useKeyboardInset());
    keyboard.keyboardHeight = 300;
    keyboard.keyboardState = KeyboardState.OPEN;
    rerender();
    expect(result.current.value).toBe(300);
  });

  it('forgets a hide once a new keyboard starts to animate in', () => {
    keyboard.keyboardState = KeyboardState.OPEN;
    keyboard.keyboardHeight = 300;
    const { result, rerender } = renderHook(() => useKeyboardInset());
    emit('keyboardDidHide');
    keyboard.keyboardState = KeyboardState.OPENING;
    rerender();
    keyboard.keyboardState = KeyboardState.OPEN;
    rerender();
    expect(result.current.value).toBe(300);
  });
});
