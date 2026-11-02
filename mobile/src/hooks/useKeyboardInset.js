import { useEffect } from 'react';
import { AppState, Dimensions, Keyboard, Platform } from 'react-native';
import { KeyboardState, useAnimatedKeyboard, useAnimatedReaction, useDerivedValue, useSharedValue } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export function keyboardInset({ height, state, closed, fallback }) {
  'worklet';
  if (state === KeyboardState.OPENING || state === KeyboardState.CLOSING) return height;
  if (closed) return 0;
  if (height > 0) return height;
  return fallback;
}

// Reanimated only tracks the IME through WindowInsetsAnimation, so an IME shown or hidden without one (fold, Modal, resume) leaves its height stale; RN's Keyboard events still fire and settle it.
export function useKeyboardInset() {
  const keyboard = useAnimatedKeyboard();
  const { bottom } = useSafeAreaInsets();
  const closed = useSharedValue(false);
  const fallback = useSharedValue(0);

  useEffect(() => {
    const shown = (h) => {
      closed.value = false;
      fallback.value = h > 0 ? h + (Platform.OS === 'android' ? bottom : 0) : 0;
    };
    const sync = () => {
      if (typeof Keyboard.isVisible !== 'function') return;
      if (Keyboard.isVisible()) shown(Keyboard.metrics?.()?.height ?? 0);
      else if (keyboard.state.value !== KeyboardState.OPENING) closed.value = true;
    };
    const subs = [
      Keyboard.addListener('keyboardDidShow', (e) => shown(e?.endCoordinates?.height ?? 0)),
      Keyboard.addListener('keyboardDidHide', () => {
        closed.value = true;
        fallback.value = 0;
      }),
      AppState.addEventListener('change', (s) => s === 'active' && sync()),
      Dimensions.addEventListener('change', sync),
    ];
    sync();
    return () => subs.forEach((s) => s.remove());
  }, [bottom, closed, fallback, keyboard.state]);

  useAnimatedReaction(
    () => keyboard.state.value,
    (state) => {
      if (state === KeyboardState.OPENING) closed.value = false;
    },
  );

  return useDerivedValue(() =>
    keyboardInset({ height: keyboard.height.value, state: keyboard.state.value, closed: closed.value, fallback: fallback.value }),
  );
}
